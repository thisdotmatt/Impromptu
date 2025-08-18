import asyncio
from typing import Any, Dict

from config import MAX_RETRIES
from executor import Executor
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from utils.helpers import formatSSEMessage
from utils.types import EventCallback, Status, WorkflowState, sse_headers
from workflows.ManufacturingWorkflow import ManufacturingWorkflow
from workflows.NetlistWorkflow import NetlistWorkflow, simulate_tool, verify_tool
from workflows.SpecWorkflow import SpecWorkflow

app = FastAPI(title="Impromptu API")

# each user of the API gets their own queue with key run_id
event_queues: Dict[str, asyncio.Queue] = {}


# we use this callback to update our queue from within the orchestrator
# it's actually pretty straightforward - functions call the event callback to say
# "hey, we have a new update!" and the callback adds the message to the queue
# our event_stream then reads from this queue sends this server-side event to the user
def getCallback(run_id: str) -> EventCallback:
    queue = event_queues.setdefault(run_id, asyncio.Queue())

    async def on_event(event_type: str, payload: Dict[str, Any]):
        await queue.put({"type": event_type, **payload})

    return on_event


async def orchestrate_workflows(run_id: str, payload: Dict, updateCallback: EventCallback):
    print("Starting the orchestration of workflows")
    queue = event_queues.setdefault(run_id, asyncio.Queue())

    # parse payload (unused at the moment)
    user_input = payload.get("userInput") or ""
    conversation_context = payload.get("conversationContext") or ""
    selected_model = payload.get("selectedModel") or "gpt-4"
    retry_from_stage = (payload.get("retryFromStage") or "spec_generation").lower()

    print(f"User input found: {user_input}")

    # run orchestrator script
    spec_workflow = SpecWorkflow()
    netlist_workflow = NetlistWorkflow(tools={"simulate": simulate_tool, "verify": verify_tool})
    manufacturing_workflow = ManufacturingWorkflow()
    workflows = {
        "spec_generation": spec_workflow,
        "netlist_generation": netlist_workflow,
        "manufacturing": manufacturing_workflow,
    }

    state = WorkflowState(
        current_workflow=None,
        context={
            "user_input": user_input
        },  # just have the first entry in the conversation at the moment
        memory={
            "conversation_context": conversation_context,
            "selected_model": selected_model,
            "retry_from_stage": retry_from_stage,
        },
        current_stage=None,
        status=Status.PENDING,
    )

    executor = Executor(state, workflows)
    new_state = await executor.run(updateCallback, max_retries=MAX_RETRIES)
    # executor.display()
    if new_state.context.get("status") == Status.ERROR:
        print(f"Executor failed with error: {new_state.context.get('err_message')}")

    executor.display()

    # await queue.put({"type": "result", "payload": formatSSEMessage(new_state)})
    await queue.put({"type": "complete"})


async def event_stream(run_id: str):
    queue = event_queues.setdefault(run_id, asyncio.Queue())
    while True:
        event = await queue.get()
        yield formatSSEMessage(event)
        if event.get("type") == "complete":
            break


@app.post("/create/{run_id}")
async def create(run_id: str, request: Request):
    payload = await request.json()
    print("Got to here, creating task")
    updateCallback = getCallback(run_id)
    asyncio.create_task(orchestrate_workflows(run_id, payload, updateCallback))
    return StreamingResponse(event_stream(run_id), headers=sse_headers)
