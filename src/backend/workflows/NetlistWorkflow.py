from typing import Dict, List, Callable
from agents.NetlistAgent import NetlistAgent
from utils.types import WorkflowState, Status
from workflows.BaseWorkflow import BaseWorkflow
import time

class NetlistWorkflow(BaseWorkflow):
    '''
    Workflow for generating a netlist from an engineering specification and verifying it using external tools
    '''
    def __init__(self, tools: Dict[str, List[Callable]] = None):
        self.agent = NetlistAgent()
        self.tools = tools

    def run(self, state: WorkflowState, max_retries: int = 1) -> WorkflowState:
        if state.context.get("spec") == None:
            state.status = Status.ERROR
            state.err_message = f"Error during workflow {state.current_workflow}: missing \'spec\' field in state.context"
            return state
        
        attempt = 0
        while attempt < max_retries:
            attempt += 1

            state.current_stage = "generate"
            state.status = Status.RUNNING
            prompt = state.context.get("spec")
            agent_response = self.agent.run(prompt=prompt)
            if agent_response.status == Status.ERROR:
                state.status = Status.ERROR
                state.err_message = f"Error during workflow {state.current_workflow} while executing agent: {agent_response.err_message}"
                return state
            
            state.context["netlist"] = agent_response.response

            # run the tools to verify the netlist is correct
            all_tools_passed = True
            hasTools = len(list(self.tools.keys())) != 0
            if hasTools:
                for tool_name in self.tools:
                    print(f"Running tool: {tool_name}")
                    state.current_stage = tool_name
                    state.status = Status.RUNNING
                    
                    state = self.tools[tool_name](state)
                    print(f"Status for tool {tool_name}: {state.status}")
                    
                    if state.status == Status.ERROR:
                        all_tools_passed = False
                        break

            if all_tools_passed: # else retry/fail
                state.status = Status.SUCCESS
                return state

        print("GOT TO HERE")
        state.status = Status.ERROR
        state.err_message = f"Error during workflow {state.current_workflow} while running stage {state.current_stage}: {state.err_message}"
        return state


def simulate_tool(state: WorkflowState):
    time.sleep(1)
    if state.context.get("fail_simulation", False): # sneaky way to allow us to test this by forcing it to fail
        state.status = Status.ERROR
        state.err_message = f"Induced failed simulation"
        return state
    state.context["simulation_result"] = {"result": "Done"}
    return state


def verify_tool(state: WorkflowState):
    time.sleep(1)
    if state.context.get("fail_verification", False): # sneaky way to allow us to test this by forcing it to fail
        state.status = Status.ERROR
        state.err_message = f"Induced failed verification"
        return state
    state.context["verification_result"] = {"result": "Done"}
    return state
