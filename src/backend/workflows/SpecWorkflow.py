from agents.SpecAgent import SpecAgent
from utils.types import Status, WorkflowState
from workflows.BaseWorkflow import BaseWorkflow


class SpecWorkflow(BaseWorkflow):
    """
    Simple workflow that executes the Specification Agent once.
    """

    def __init__(self):
        self.agent = SpecAgent()

    def run(self, state: WorkflowState) -> WorkflowState:
        if state.context.get("user_input") == None:
            state.status = Status.ERROR
            state.err_message = f"Error during workflow {state.current_workflow}: missing 'user_input' field in state.context"
            return state

        state.current_stage = "generate"
        state.status = Status.RUNNING

        prompt = state.context.get("user_input")
        agent_response = self.agent.run(prompt=prompt)
        if agent_response.status == Status.ERROR:
            state.status = Status.ERROR
            state.err_message = f"Error during workflow {state.current_workflow} while executing agent: {agent_response.err_message}"
            return state

        state.context["spec"] = agent_response.response
        state.status = Status.SUCCESS
        return state
