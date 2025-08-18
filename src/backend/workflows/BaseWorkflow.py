from abc import ABC as AbstractBaseClass
from abc import abstractmethod
from typing import Awaitable, Dict, List

from utils.types import EventCallback, WorkflowState


class BaseWorkflow(AbstractBaseClass):
    def __init__(self, tools: Dict[str, List[Awaitable]] = None):
        self.tools = tools  # deterministic, non-LLM tools

    @abstractmethod
    async def run(
        self, state: WorkflowState, updateCallback: EventCallback, max_retries: int = 1
    ) -> WorkflowState:
        """
        Runs the end-to-end workflow while updating the upstream workflow orchestrator.
        Args:
            state: WorkflowState represents the stored memory provided by the orchestrator, your workflow will edit the state and return it
            updateCallback: this is the method that is used to update the orchestrator with what is currently happening (e.g. "I am still running")
            max_retries: allows the workflow to loop a certain number of times before failing
        """
        pass
