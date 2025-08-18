from datetime import datetime, timezone

from agents.SpecAgent import SpecAgent
from utils.types import EventCallback, Status, WorkflowState
from workflows.BaseWorkflow import BaseWorkflow


class SpecWorkflow(BaseWorkflow):
    """
    Simple workflow that executes the Specification Agent once.
    """

    def __init__(self):
        self.agent = SpecAgent()

    async def run(self, state: WorkflowState, updateCallback: EventCallback) -> WorkflowState:
        if state.context.get("user_input") == None:
            state.status = Status.ERROR
            state.err_message = f"Error during workflow {state.current_workflow}: missing 'user_input' field in state.context"
            return state

        if state.memory.get("conversation_context") == None:
            state.status = Status.ERROR
            state.err_message = f"Error during workflow {state.current_workflow}: missing 'conversation_context' field in state.memory"
            return state

        workflow_name = state.current_workflow or "spec_generation"
        state.current_stage = "generate"
        state.status = Status.RUNNING

        await updateCallback(
            "substage_started",
            {
                "type": "substage_started",
                "workflow": workflow_name,
                "substage": "generate",
                "step_index": 1,
                "ts": datetime.now(timezone.utc).isoformat(),
            },
        )

        prompt = f"""High-level request: {state.context.get('user_input')}\nConversation with Electrical Engineering Chatbot: {state.memory.get('conversation_context')}"""
        print("Specification prompt: ", prompt)
        agent_response = await self.agent.run(prompt=prompt)
        if agent_response.status == Status.ERROR:
            state.status = Status.ERROR
            state.err_message = f"Error during workflow {state.current_workflow} while executing agent: {agent_response.err_message}"
            return state

        result_name = f"{workflow_name}_result"
        state.context[result_name] = agent_response.response
        state.status = Status.SUCCESS

        await updateCallback(
            "substage_completed",
            {
                "type": "substage_completed",
                "workflow": workflow_name,
                "substage": "generate",
                "step_index": 1,
                "ts": datetime.now(timezone.utc).isoformat(),
                "meta": {},
            },
        )

        return state
