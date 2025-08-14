from typing import Any, Callable, Dict, List

from agents.NetlistAgent import NetlistAgent
from utils.usage import UsageTracker


class NetlistWorkflow:
    def __init__(self, tracker: UsageTracker, tools: List[Callable], max_retries: int = 3):
        self.agent = NetlistAgent(tracker)
        self.tools = tools
        self.tracker = tracker
        self.max_retries = max_retries

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        attempt = 0
        while attempt < self.max_retries:
            attempt += 1
            state["netlist_attempt"] = attempt

            # generates netlist
            state = self.agent.run(state)

            # here we run Ngspice/KiCad tools (for now I've left them blank)
            all_passed = True
            for tool in self.tools:
                state, success = tool(state)
                if not success:
                    all_passed = False
                    break

            if all_passed:
                state["netlist_status"] = "success"
                return state

        state["netlist_status"] = "failed"
        raise RuntimeError("Netlist workflow failed after all retries.")


def simulate_tool(state: Dict[str, Any]):
    """Example simulation tool — fails if 'fail_simulation' flag in state."""
    if state.get("fail_simulation", False):
        return state, False
    return state, True


def verify_tool(state: Dict[str, Any]):
    """Example verification tool — fails if 'fail_verification' flag in state."""
    if state.get("fail_verification", False):
        return state, False
    return state, True
