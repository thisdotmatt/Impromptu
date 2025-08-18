from typing import Dict, List, Awaitable
from datetime import datetime, timezone
import asyncio

from utils.types import Status, WorkflowState, EventCallback
from workflows.BaseWorkflow import BaseWorkflow


class ManufacturingWorkflow(BaseWorkflow):
    def __init__(self, tools: Dict[str, List[Awaitable]] = None):
        self.tools = tools

    async def run(self, state: WorkflowState, updateCallback: EventCallback) -> WorkflowState:
        workflow_name = state.current_workflow or "manufacture"
        state.status = Status.RUNNING

        await updateCallback(
            "substage_started",
            {
                "type": "substage_started",
                "workflow": workflow_name,
                "substage": "manufacture",
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
                "workflow": state.current_workflow or "manufacturing",
                "substage": "manufacture",
                "step_index": 1,
                "ts": datetime.now(timezone.utc).isoformat(),
                "meta": {},
            },
        )
        return state
