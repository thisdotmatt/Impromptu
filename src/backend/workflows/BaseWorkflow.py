from typing import Dict, Any, List, Callable
from abc import ABC as AbstractBaseClass, abstractmethod
from utils.usage import UsageTracker

class BaseWorkflow(AbstractBaseClass):
    def __init__(self, tracker: UsageTracker, tools: List[Callable] = None):
        self.tracker = tracker # to be passed to whatever agent(s) your instantiate
        self.tools = tools # deterministic, non-LLM tools

    @abstractmethod
    def run(self, state: Dict[str, Any], onUpdate: Callable = None, max_retries: int=1) -> Dict[str, Any]:
        """
        Runs the end-to-end workflow while updating the upstream workflow orchestrator.
        Args: 
            state: Dict[str, Any] represents the stored memory provided by the orchestrator, your workflow will edit the state and return it
            onUpdate: this is the method that is used to update the orchestrator with what is currently happening (e.g. "I am still running")
            max_retries: allows the workflow to loop a certain number of times before failing
        """
        pass