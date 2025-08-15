from typing import Callable, Dict, Optional
import time

from utils.types import WorkflowContext, WorkflowState, Status
from config import MAX_RETRIES, MAX_RUN_COST
from langchain_community.callbacks import get_openai_callback

class WorkflowOrchestrator:
    '''
    Orchestrates a set of workflows, each with its own WorkflowState.
    '''
    def __init__(self, workflows: Dict[str, Callable], max_retries: int = MAX_RETRIES):
        """
        workflows: dictionary mapping workflow_name to the function to run that workflow
        max_retries: retries per workflow if it fails
        """
        self.workflows = workflows
        self.max_retries = max_retries

    def _calculateTotalSpend(self, workflow_state: WorkflowState) -> float:
        return round(sum(float(workflow_state.workflows_context[workflow_name].cost or 0.0) for workflow_name in workflow_state.workflows_context.keys()), 6)
    
    def _calculateTotalTokens(self, workflow_state: WorkflowState) -> int:
        return sum(workflow_state.workflows_context[workflow_name].total_tokens for workflow_name in workflow_state.workflows_context.keys())

    def runWorkflows(self, workflow_state: WorkflowState) -> WorkflowState:
        for workflow_name, workflow_callable in self.workflows.items():
            # stop before entering loop if we're already at/over the limit
            if MAX_RUN_COST is not None and self._calculateTotalSpend(workflow_state) >= MAX_RUN_COST:
                workflow_state.status = Status.ERROR
                total_spend = self._calculateTotalSpend(workflow_state)
                total_tokens = self._calculateTotalTokens(self, workflow_state)
                workflow_state.err_message = f"Cost limit reached: ${total_spend:.6f} for {total_tokens} tokens (limit: ${MAX_RUN_COST:.6f})"
                
                return workflow_state

            workflow_state.current_workflow = workflow_name
            workflow_state.status = Status.PENDING

            # initialize workflow context (tracks duration, tokens, cost, etc.)
            start_time_ns = time.perf_counter_ns()
            workflow_context = WorkflowContext(start_time_ns=start_time_ns)
            workflow_state.workflows_context[workflow_state.current_workflow] = workflow_context

            last_error_message: Optional[str] = None
            attempt = 0
            while attempt < self.max_retries:
                attempt += 1
                workflow_state.status = Status.RUNNING

                exception_in_workflow: Optional[Exception] = None
                # wrapped in openai callback to get tokens/cost
                with get_openai_callback() as callback:
                    try:
                        workflow_state = workflow_callable(workflow_state)
                    except Exception as e:
                        exception_in_workflow = e

                # calculate costs/tokens
                workflow_context.input_tokens += int(getattr(callback, "prompt_tokens", 0) or 0)
                workflow_context.output_tokens += int(getattr(callback, "completion_tokens", 0) or 0)
                workflow_context.total_tokens += int(getattr(callback, "total_tokens", 0) or 0)
                workflow_context.cost += float(getattr(callback, "total_cost", 0.0) or 0.0)

                if exception_in_workflow is not None:
                    workflow_state.status = Status.ERROR
                    last_error_message = f"Unhandled exception in '{workflow_name}': {exception_in_workflow}"

                # budget check
                total_spend = self._calculateTotalSpend(workflow_state)
                if MAX_RUN_COST is not None and total_spend > MAX_RUN_COST:
                    workflow_state.status = Status.ERROR
                    workflow_state.err_message = f"Cost limit exceeded: ${total_spend:.6f} (limit: ${MAX_RUN_COST:.6f})"
                    break

                # if we succeed, move onto the next workflow
                if workflow_state.status == Status.SUCCESS:
                    break
                
                if not workflow_state.err_message:
                    workflow_state.err_message = last_error_message or f"Workflow '{workflow_name}' failed after {attempt} attempt(s)."

            # get duration
            end_time_ns = time.perf_counter_ns()
            workflow_context.end_time_ns = end_time_ns
            workflow_context.duration_ns = int(end_time_ns - start_time_ns)

            # If this workflow did not succeed, stop the run
            if workflow_state.status != Status.SUCCESS:
                return workflow_state

        workflow_state.status = Status.SUCCESS
        workflow_state.err_message = ""
        return workflow_state