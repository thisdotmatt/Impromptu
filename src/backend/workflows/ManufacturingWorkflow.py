from typing import Callable, Dict, List

from utils.types import Status, WorkflowState
from workflows.BaseWorkflow import BaseWorkflow


class ManufacturingWorkflow(BaseWorkflow):
    def __init__(self, tools: Dict[str, List[Callable]] = None):
        self.tools = tools  # deterministic, non-LLM tools

    def run(self, state: WorkflowState) -> WorkflowState:
        state.status = Status.SUCCESS
        return state
