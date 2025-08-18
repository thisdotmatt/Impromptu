import asyncio
from datetime import datetime, timezone
from typing import Awaitable, Dict, List

from agents.NetlistAgent import NetlistAgent
from utils.types import EventCallback, Status, WorkflowState
from workflows.BaseWorkflow import BaseWorkflow


class NetlistWorkflow(BaseWorkflow):
    """
    Workflow for generating a netlist from an engineering specification and verifying it using external tools
    """

    def __init__(self, tools: Dict[str, List[Awaitable]] = None):
        self.agent = NetlistAgent()
        self.tools = tools

    async def run(
        self, state: WorkflowState, updateCallback: EventCallback, max_retries: int = 1
    ) -> WorkflowState:
        if state.context.get("spec_generation_result") == None:
            state.status = Status.ERROR
            state.err_message = f"Error during workflow {state.current_workflow}: missing 'spec' field in state.context"
            return state

        workflow_name = state.current_workflow or "netlist_generation"

        attempt = 0
        while attempt < max_retries:
            attempt += 1

            step_index = 0

            # generate stage
            state.current_stage = "generate"
            state.status = Status.RUNNING
            step_index += 1
            await updateCallback(
                "substage_started",
                {
                    "type": "substage_started",
                    "workflow": workflow_name,
                    "substage": state.current_stage,
                    "step_index": step_index,
                    "ts": datetime.now(timezone.utc).isoformat(),
                },
            )

            prompt = state.context.get("spec_generation_result")
            agent_response = await self.agent.run(prompt=prompt)
            if agent_response.status == Status.ERROR:
                state.status = Status.ERROR
                state.err_message = f"Error during workflow {state.current_workflow} while executing agent: {agent_response.err_message}"
                return state

            result_name = f"{workflow_name}_result"
            state.context[result_name] = agent_response.response

            # generate completed
            await updateCallback(
                "substage_completed",
                {
                    "type": "substage_completed",
                    "workflow": workflow_name,
                    "substage": state.current_stage,
                    "step_index": step_index,
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "meta": {},
                },
            )

            # run the tools to verify the netlist is correct
            all_tools_passed = True
            hasTools = self.tools is not None and len(list(self.tools.keys())) != 0
            if hasTools:
                for tool_name in self.tools:
                    # tool stage
                    state.current_stage = tool_name
                    state.status = Status.RUNNING
                    step_index += 1
                    await updateCallback(
                        "substage_started",
                        {
                            "type": "substage_started",
                            "workflow": workflow_name,
                            "substage": state.current_stage,
                            "step_index": step_index,
                            "ts": datetime.now(timezone.utc).isoformat(),
                        },
                    )

                    state = await self.tools[tool_name](state)

                    if state.status == Status.ERROR:
                        all_tools_passed = False
                        break

                    await updateCallback(
                        "substage_completed",
                        {
                            "type": "substage_completed",
                            "workflow": workflow_name,
                            "substage": state.current_stage,
                            "step_index": step_index,
                            "ts": datetime.now(timezone.utc).isoformat(),
                            "meta": {},
                        },
                    )

            if all_tools_passed:  # else retry/fail
                state.status = Status.SUCCESS
                return state

        state.status = Status.ERROR
        state.err_message = f"Error during workflow {state.current_workflow} while running stage {state.current_stage}: {state.err_message}"
        return state


async def simulate_tool(state: WorkflowState):
    await asyncio.sleep(0.5)
    if state.context.get(
        "fail_simulation", False
    ):  # sneaky way to allow us to test this by forcing it to fail
        state.status = Status.ERROR
        state.err_message = "Induced failed simulation"
        return state
    state.context["simulation_result"] = {"result": "Done"}
    return state


async def verify_tool(state: WorkflowState):
    await asyncio.sleep(0.5)
    if state.context.get(
        "fail_verification", False
    ):  # sneaky way to allow us to test this by forcing it to fail
        state.status = Status.ERROR
        state.err_message = "Induced failed verification"
        return state
    state.context["verification_result"] = {"result": "Done"}
    return state
