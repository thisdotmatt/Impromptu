import asyncio
import json
import time
from typing import Any, Dict, Optional, Tuple

from config import USE_MOCK_LLM  # project-level config flag
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from orchestrator.orchestrator import WorkflowOrchestrator
from utils.usage import UsageTracker
from workflows.NetlistWorkflow import NetlistWorkflow, simulate_tool, verify_tool
from workflows.SpecWorkflow import SpecWorkflow

app = FastAPI(title="Orchestrator SSE Bridge")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_ui_token_cost(node_usage: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map tracker aggregate keys -> UI tokenCost shape.
    """
    return {
        "inputTokens": int(node_usage.get("prompt_tokens", 0) or 0),
        "outputTokens": int(node_usage.get("completion_tokens", 0) or 0),
        "totalTokens": int(node_usage.get("total_tokens", 0) or 0),
        "estimatedCost": float(node_usage.get("total_cost", 0.0) or 0.0),
    }


def _sse_line(payload: Dict[str, Any]) -> bytes:
    return f"data: {json.dumps(payload)}\n\n".encode("utf-8")


def _extract_requirements(body: Dict[str, Any]) -> str:
    requirements = (body.get("requirements") or "").strip()
    if not requirements:
        convo = body.get("conversationContext") or []
        user_msgs = [m for m in convo if m.get("role") == "user" and m.get("content")]
        if user_msgs:
            requirements = user_msgs[-1]["content"]
    return requirements or "No specific requirements provided"


def _map_substage(substage: Optional[str]) -> Optional[str]:
    if substage in (None, ""):
        return None
    if substage == "simulate_tool":
        return "simulate"
    if substage == "verify_tool":
        return "verify"
    return substage


def _now_ms() -> int:
    return int(time.time() * 1000)


def _default_token_cost(stage: str) -> Optional[Dict[str, Any]]:
    """
    When mocking, provide non-zero defaults (matches your reference route).
    When using a real LLM, return None so the UI hides the green box if
    there’s no usage to show.
    """
    if not USE_MOCK_LLM:
        return None
    base = {
        "spec": (1200, 800),
        "design": (2000, 1500),
        "manufacturing": (1500, 900),
    }
    inp, out = base.get(stage, (1000, 500))
    total = inp + out
    # Mock pricing same as your reference
    est = (inp / 1000) * 0.01 + (out / 1000) * 0.03
    return {
        "inputTokens": inp,
        "outputTokens": out,
        "totalTokens": total,
        "estimatedCost": round(est, 6),
    }


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@app.post("/orchestrator/run")
async def run_orchestrator(request: Request) -> StreamingResponse:
    body = await request.json()
    selected_model = body.get("selectedModel") or "gpt-4"
    retry_from_stage = (body.get("retryFromStage") or "spec").lower()
    requirements = _extract_requirements(body)

    queue: asyncio.Queue[bytes] = asyncio.Queue()
    loop = asyncio.get_running_loop()

    async def emit(payload: Dict[str, Any]) -> None:
        await queue.put(_sse_line(payload))

    tracker = UsageTracker()
    spec_workflow = SpecWorkflow(tracker)
    netlist_workflow = NetlistWorkflow(tracker, tools=[simulate_tool, verify_tool])

    # Decide which workflows to run
    if retry_from_stage == "design":
        workflows = [
            (
                "netlist_generation",
                lambda *args, **kwargs: netlist_workflow.run(*args, **kwargs, max_retries=1),
            )
        ]
    elif retry_from_stage == "manufacturing":
        workflows = []  # we'll only emit manufacturing mock
    else:
        workflows = [
            (
                "spec_generation",
                lambda *args, **kwargs: spec_workflow.run(*args, **kwargs, max_retries=1),
            ),
            (
                "netlist_generation",
                lambda *args, **kwargs: netlist_workflow.run(*args, **kwargs, max_retries=1),
            ),
        ]

    orchestrator = WorkflowOrchestrator(workflows=workflows, tracker=tracker, max_retries=1)

    # Map orchestrator names -> UI stage ids
    stage_map = {
        "spec_generation": "spec",
        "netlist_generation": "design",
    }

    # Timing & status tracking (thread-safe enough for our usage)
    stage_t0_mono: Dict[str, float] = {}  # perf_counter start
    stage_t0_wall_ms: Dict[str, int] = {}  # wall-clock start ms
    seen_running: set[str] = set()
    stage_success: Dict[str, bool] = {"spec": False, "design": False}
    had_error = {"value": False}  # boxed to mutate inside closure

    # Best-effort aggregate lookup
    def _agg_for(stage_ui_id: str) -> Optional[Dict[str, Any]]:
        """
        Try to pull per-stage aggregate from tracker.
        We accept both old/new tracker implementations; fail silently if absent.
        """
        # orchestrator internal keys:
        key_map = {"spec": "spec_generation", "design": "netlist_generation"}
        tracker_key = key_map.get(stage_ui_id, None)
        if not tracker_key:
            return None
        try:
            if hasattr(tracker, "aggregate_tokens_for_stage"):
                agg = tracker.aggregate_tokens_for_stage(tracker_key, include_children=True)  # type: ignore[attr-defined]
                if agg:
                    return _to_ui_token_cost(agg)
        except Exception as e:
            # Don’t blow up the stream if usage isn’t available
            print(f"[usage] aggregate failed for {tracker_key}: {e}")
        return None

    def _finish_timing_for(ui_stage: str) -> Tuple[int, int, int]:
        """
        Returns (startTimeMs, endTimeMs, durationMs).
        If we never saw 'running', synthesize a near-now start.
        """
        end_ms = _now_ms()
        t0_mono = stage_t0_mono.get(ui_stage)
        if t0_mono is None:
            stage_t0_mono[ui_stage] = time.perf_counter()
            stage_t0_wall_ms[ui_stage] = end_ms - 1
            t0_mono = stage_t0_mono[ui_stage]
        start_ms = stage_t0_wall_ms.get(ui_stage, end_ms - 1)
        duration_ms = max(0, int((time.perf_counter() - t0_mono) * 1000))
        return start_ms, end_ms, duration_ms

    def _per_stage_token_cost(stage_ui_id: str) -> Optional[Dict[str, Any]]:
        """
        1) if update provided node usage, the orchestrator will pass it (handled below)
        2) otherwise try tracker aggregate (real LLM)
        3) otherwise, if mock mode, return a mocked non-zero default for that stage
        """
        agg = _agg_for(stage_ui_id)
        if agg:
            return agg
        return _default_token_cost(stage_ui_id)  # None when real LLM & no usage

    def onUpdate(workflow_name: str, update: Dict[str, Any]):
        """
        Translate orchestrator callbacks into UI-compatible SSE messages.
        Runs in a *worker thread*, so we must schedule all emits on the main loop.
        """
        ui_stage = stage_map.get(workflow_name, workflow_name)
        status = update.get("status")
        sub_stage = _map_substage(update.get("subStage"))

        # First top-level 'running' → mark start and emit with startTimeMs
        if status == "running" and not sub_stage:
            if ui_stage not in seen_running:
                seen_running.add(ui_stage)
                stage_t0_mono.setdefault(ui_stage, time.perf_counter())
                stage_t0_wall_ms.setdefault(ui_stage, _now_ms())
                loop.call_soon_threadsafe(
                    asyncio.create_task,
                    emit(
                        {
                            "stage": ui_stage,
                            "status": "running",
                            "startTimeMs": stage_t0_wall_ms[ui_stage],
                        }
                    ),
                )
            return  # nothing else to send for a 'running' tick

        # If we never sent 'running' but get success/error, synthesize it so UI has a start
        if not sub_stage and ui_stage not in seen_running:
            seen_running.add(ui_stage)
            stage_t0_mono.setdefault(ui_stage, time.perf_counter())
            stage_t0_wall_ms.setdefault(ui_stage, _now_ms())
            loop.call_soon_threadsafe(
                asyncio.create_task,
                emit(
                    {
                        "stage": ui_stage,
                        "status": "running",
                        "startTimeMs": stage_t0_wall_ms[ui_stage],
                    }
                ),
            )
            # fall through to also emit the completion payload

        # Sub-stage updates stream straight through
        if sub_stage:
            loop.call_soon_threadsafe(
                asyncio.create_task,
                emit({"stage": ui_stage, "subStage": sub_stage, "status": status}),
            )
            return

        # Top-level completion or error → include timing + tokenCost + result if any
        start_ms, end_ms, duration_ms = _finish_timing_for(ui_stage)
        payload: Dict[str, Any] = {
            "stage": ui_stage,
            "status": status,
            "startTimeMs": start_ms,
            "endTimeMs": end_ms,
            "durationMs": duration_ms,
        }

        # Orchestrator might attach raw node usage; convert if present
        node_usage = update.get("tokenCost")
        if node_usage:
            payload["tokenCost"] = _to_ui_token_cost(node_usage)

        if status == "success":
            if ui_stage in stage_success:
                stage_success[ui_stage] = True

            if ui_stage == "spec":
                payload["result"] = f'Specification generated from requirements: "{requirements}".'
                payload.setdefault("tokenCost", _per_stage_token_cost("spec"))

            elif ui_stage == "design":
                # Prefer explicit netlist if provided; otherwise any "result" string
                netlist_text = (update.get("netlist") or update.get("result") or "").strip()
                print("Yo Netlist: " + netlist_text)
                if netlist_text:
                    payload["result"] = f"Generated netlist:\n\n{netlist_text}"
                else:
                    payload["result"] = "Netlist pipeline complete: generate → simulate → verify."
                payload.setdefault("tokenCost", _per_stage_token_cost("design"))

        elif status == "error":
            had_error["value"] = True
            payload["result"] = str(update.get("result") or "An error occurred.")
            # If no node usage, try to attach what we can
            payload.setdefault("tokenCost", _per_stage_token_cost(ui_stage))

        loop.call_soon_threadsafe(asyncio.create_task, emit(payload))

    async def manufacturing_mock():
        """
        Mocked manufacturing with proper timing + tokenCost.
        """
        start_ms = _now_ms()
        t0 = time.perf_counter()
        await emit({"stage": "manufacturing", "status": "running", "startTimeMs": start_ms})

        # Substages
        for sub_id, delay in [("placement", 0.30), ("machine", 0.35), ("verify", 0.25)]:
            await emit({"stage": "manufacturing", "subStage": sub_id, "status": "running"})
            await asyncio.sleep(delay)
            await emit({"stage": "manufacturing", "subStage": sub_id, "status": "success"})

        result_text = (
            "Manufacturing setup complete:\n"
            "✓ Placement data generated\n"
            "✓ Pick-and-place machine ready\n"
            "✓ Estimated assembly time: ~3 minutes\n\n"
            "Component coordinates:\n- U1: (15.2, 8.7, 0°)\n- C1: (12.1, 6.3, 90°)\n"
            "- R1: (18.4, 10.2, 0°)\n- L1: (20.8, 8.9, 270°)"
        )

        duration_ms = max(0, int((time.perf_counter() - t0) * 1000))
        end_ms = _now_ms()

        await emit(
            {
                "stage": "manufacturing",
                "status": "success",
                "result": result_text,
                "tokenCost": _default_token_cost("manufacturing") or None,
                "startTimeMs": start_ms,
                "endTimeMs": end_ms,
                "durationMs": duration_ms,
            }
        )

    async def orchestrate_and_stream():
        """
        Run orchestrator in a worker thread; stream updates as they arrive.
        Only run manufacturing if design ran and no errors occurred (or when explicitly requested).
        """
        try:
            initial_state: Dict[str, Any] = {
                "user_input": requirements,
                "usage": {"nodes": {}},
                "memory": {},
                # knobs you can flip during testing:
                "fail_simulation": False,
                "fail_verification": False,
            }

            if workflows:
                # Run workflows directly in main event loop (no thread)
                # This allows onUpdate callbacks to be processed immediately
                import concurrent.futures

                def run_orchestrator_sync():
                    return orchestrator.run_workflows(initial_state, onUpdate)

                # Use ThreadPoolExecutor with a single thread to allow GIL release
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(run_orchestrator_sync)
                    # Check for completion periodically to allow other coroutines to run
                    while not future.done():
                        await asyncio.sleep(0.1)  # Yield control frequently
                    result = future.result()

                ran_design = any(name == "netlist_generation" for name, _ in workflows)
                if ran_design and not had_error["value"] and stage_success.get("design"):
                    await manufacturing_mock()
            else:
                # retryFromStage == "manufacturing"
                await manufacturing_mock()

        finally:
            # Sentinel to close the SSE stream
            await queue.put(b"")

    async def event_generator():
        asyncio.create_task(orchestrate_and_stream())
        while True:
            chunk = await queue.get()
            if chunk == b"":
                break
            yield chunk

    headers = {
        # Proper SSE content type to avoid client-side buffering
        "Content-Type": "text/event-stream; charset=utf-8",
        # Prevent intermediary/proxy buffering (e.g., nginx) of the stream
        "X-Accel-Buffering": "no",
        # Keep the connection open and prevent caching
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
    }
    return StreamingResponse(event_generator(), media_type="text/event-stream", headers=headers)
