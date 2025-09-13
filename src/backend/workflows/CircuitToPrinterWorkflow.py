from datetime import datetime, timezone
from typing import Awaitable, Dict, List

from config import MOCK_GCODE
from utils.types import EventCallback, Status, WorkflowState
from workflows.BaseWorkflow import BaseWorkflow
import time
import asyncio


class CircuitToPrinterWorkflow(BaseWorkflow):
    def __init__(self, tools: Dict[str, List[Awaitable]] = None):
        self.tools = tools

    async def run(self, state: WorkflowState, updateCallback: EventCallback) -> WorkflowState:
        workflow_name = state.current_workflow or "circuit_to_printer"
        state.status = Status.RUNNING

        await updateCallback(
            "substage_started",
            {
                "type": "substage_started",
                "workflow": workflow_name,
                "substage": "circuit_to_printer",
                "step_index": 1,
                "ts": datetime.now(timezone.utc).isoformat(),
            },
        )

        # TODO: finish this whole verified netlist to routed circuit to GCODE pipeline
        state.status = Status.SUCCESS
        result_name = f"{workflow_name}_result"
        state.context[result_name] = {"routing": "No routing available.\n", "gcode": MOCK_GCODE}
        await asyncio.sleep(1) # TODO: remove

        await updateCallback(
            "substage_completed",
            {
                "type": "substage_completed",
                "workflow": state.current_workflow or "circuit_to_printer",
                "substage": "circuit_to_printer",
                "step_index": 1,
                "ts": datetime.now(timezone.utc).isoformat(),
                "meta": {},
            },
        )
        return state
