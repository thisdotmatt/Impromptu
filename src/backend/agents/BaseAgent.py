from abc import ABC as AbstractBaseClass
from abc import abstractmethod

from utils.types import AgentResponse


class BaseAgent(AbstractBaseClass):
    def __init__(self):
        pass

    @abstractmethod
    def _mock(self, prompt: str) -> AgentResponse:
        """
        Generate a mock response for the given prompt.

        This method should return a mocked result formatted as expected by the agent.
        It is intended for use when API calls should be avoided, such as when
        USE_MOCK_LLM is set to True in the configuration, to prevent unnecessary
        expenditure of API credits.
        """
        pass

    @abstractmethod
    def run(self, prompt: str) -> AgentResponse:
        """
        Processes the provided prompt and generates a response with an error message
        This method is designed to be highly customizable, allowing derived agents to implement
        specific behaviors such as handling user input or tracking usage metrics.
        """
        pass
