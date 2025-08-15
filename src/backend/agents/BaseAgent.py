from abc import ABC as AbstractBaseClass, abstractmethod
from utils.usage import UsageTracker
from typing import Any, Dict

class BaseAgent(AbstractBaseClass):
    def __init__(self, usage_tracker: UsageTracker):
        self.usage_tracker = usage_tracker
        
    @abstractmethod
    def _mock(self, prompt: str) -> str:
        """
        Generate a mock response for the given prompt.

        This method should return a mocked result formatted as expected by the agent.
        It is intended for use when API calls should be avoided, such as when
        USE_MOCK_LLM is set to True in the configuration, to prevent unnecessary
        expenditure of API credits.
        """
        pass

    @abstractmethod
    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processes the provided state dictionary, interacts with the language model as needed, and updates the state accordingly.
        This method is designed to be highly customizable, allowing derived agents to implement specific behaviors such as handling user input or tracking usage metrics.
        """
        pass
