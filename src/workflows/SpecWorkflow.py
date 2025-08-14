from typing import Any, Dict

from agents.SpecAgent import SpecAgent
from utils.usage import UsageTracker


class SpecWorkflow:
    def __init__(self, tracker: UsageTracker):
        self.agent = SpecAgent(tracker)

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        return self.agent.run(state)
