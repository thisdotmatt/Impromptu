from typing import Any, Dict, Callable, Optional

from agents.SpecAgent import SpecAgent
from utils.usage import UsageTracker
from workflows.BaseWorkflow import BaseWorkflow


class SpecWorkflow(BaseWorkflow):
    '''
    Simple workflow that executes the Specification Agent once.
    '''
    def __init__(self, tracker: UsageTracker):
        self.agent = SpecAgent(tracker)
        self.tracker = tracker

    def run(self, state: Dict[str, Any], onUpdate: Optional[Callable] = None, max_retries: int = 1) -> Dict[str, Any]:
        if onUpdate:
            onUpdate("spec_generation", {"status": "running"})
            
        state = self.agent.run(state)
        
        if onUpdate:
            token_cost = self.tracker.getTokenReportForAgent("spec_generation")
            onUpdate("spec_generation", {
                "status": "success", 
                "tokenCost": token_cost
            })
        
        return state
