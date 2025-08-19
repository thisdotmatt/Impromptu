from datetime import datetime, timezone
from typing import Awaitable, Dict, List

from utils.types import EventCallback, Status, WorkflowState
from workflows.BaseWorkflow import BaseWorkflow


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

        # mock processing: tools would be called here

        state.status = Status.SUCCESS

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
