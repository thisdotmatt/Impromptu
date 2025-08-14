from typing import Any, Callable, Dict, List, Optional

from config import MAX_RETRIES
from utils.usage import UsageTracker


class WorkflowOrchestrator:
    def __init__(
        self, workflows: List[tuple], tracker: UsageTracker, max_retries: int = MAX_RETRIES
    ):
        """
        workflows: list of (workflow_name, workflow_callable)
        tracker: shared UsageTracker instance
        max_retries: retries per workflow if it fails
        """
        self.workflows = workflows
        self.tracker = tracker
        self.max_retries = max_retries

    def run_workflows(
        self, state: Dict[str, Any], on_update: Optional[Callable] = None
    ) -> Dict[str, Any]:
        for workflow_name, workflow_callable in self.workflows:
            attempt = 0
            while attempt < self.max_retries:
                attempt += 1
                if on_update:
                    on_update(workflow_name, {"status": "running", "attempt": attempt})

                try:
                    state = workflow_callable(state)

                    if not self.tracker.isWithinLimit():
                        msg = f"Cost limit exceeded after workflow '{workflow_name}'"
                        if on_update:
                            on_update(workflow_name, {"status": "error", "result": msg})
                        state["budget_status"] = "over_limit"
                        return state

                    if on_update:
                        on_update(workflow_name, {"status": "success"})
                    break  # success

                except RuntimeError as e:
                    if on_update:
                        on_update(workflow_name, {"status": "error", "result": str(e)})
                    state[workflow_name + "_error"] = str(e)
                    if attempt >= self.max_retries:
                        return state
                except Exception as e:
                    if on_update:
                        on_update(workflow_name, {"status": "error", "result": str(e)})
                    if attempt >= self.max_retries:
                        return state
        return state
