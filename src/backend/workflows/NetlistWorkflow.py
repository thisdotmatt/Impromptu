from typing import Dict, Any, List, Callable
from agents.NetlistAgent import NetlistAgent
from utils.usage import UsageTracker
from workflows.BaseWorkflow import BaseWorkflow
import asyncio

class NetlistWorkflow(BaseWorkflow):
    '''
    Workflow for generating a netlist from an engineering specification and verifying it using external tools
    '''
    def __init__(self, tracker: UsageTracker, tools: List[Callable] = None):
        self.agent = NetlistAgent(tracker)
        self.tools = tools
        self.tracker = tracker

    def run(self, state: Dict[str, Any], onUpdate: Callable = None, max_retries: int = 1) -> Dict[str, Any]:
        attempt = 0
        while attempt < max_retries:
            attempt += 1
            state["netlist_attempt"] = attempt  # store the attempt count for reference

            # allows us to update the API with current running state
            if onUpdate:
                onUpdate("netlist_generation", {
                    "status": "running",
                    "attempt": attempt,
                    "subStage": "generate"
                })

            # run netlist agent and retrieve the generated netlist
            state = self.agent.run(state)

            if onUpdate: # we want to report that the LLM generation substage was successful
                token_cost = self.tracker.getTokenReportForAgent("netlist_generation")
                onUpdate("netlist_generation", {
                    "status": "completed",  # Use "completed" instead of "success" for substages
                    "subStage": "generate",
                    "tokenCost": token_cost
                })

            # run the tools to verify the netlist is correct
            all_tools_passed = True
            if self.tools:
                for tool in self.tools:
                    sub_stage_name = getattr(tool, "__name__", "tool") # neat way of getting the tool's method name
                    if onUpdate:
                        onUpdate("netlist_generation", {
                            "status": "running",
                            "subStage": sub_stage_name
                        })
                    
                    # run the tool and get the result, as well as the success/failure
                    state, success = tool(state)

                    if success:
                        if onUpdate:
                            onUpdate("netlist_generation", {
                                "status": "completed",  # Use "completed" for successful substages
                                "subStage": sub_stage_name
                            })
                    else:
                        if onUpdate:
                            onUpdate("netlist_generation", {
                                "status": "error",
                                "subStage": sub_stage_name
                            })
                        all_tools_passed = False
                        break

            if all_tools_passed: # else retry/fail
                state["netlist_status"] = "success"
                if onUpdate:
                    onUpdate("netlist_generation", {
                        "status": "success",
                        "netlist": state.get("netlist", ""),
                        "tokenCost": self.tracker.getTokenReportForAgent("netlist_generation") # calculate tokens/cost after everything is done
                    })
                return state

        state["netlist_status"] = "failed"
        raise RuntimeError("Netlist workflow failed after all retries.")


def simulate_tool(state: Dict[str, Any]):
    import time
    time.sleep(5)
    if state.get("fail_simulation", False): # sneaky way to allow us to test this by forcing it to fail
        return state, False
    return state, True


def verify_tool(state: Dict[str, Any]):
    import time
    time.sleep(5)
    if state.get("fail_verification", False): # sneaky way to allow us to test this by forcing it to fail
        return state, False
    return state, True
