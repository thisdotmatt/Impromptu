import asyncio

from orchestrator.orchestrator import WorkflowOrchestrator
from utils.types import EventCallback, Status, WorkflowState
from workflows.CircuitToPrinterWorkflow import CircuitToPrinterWorkflow
from workflows.NetlistWorkflow import NetlistWorkflow, simulate_tool, verify_tool
from workflows.SpecWorkflow import SpecWorkflow


class Executor:
    def __init__(self, state: WorkflowState, workflows: dict):
        self.state = state
        self.workflows = workflows

    async def run(self, updateCallback: EventCallback | None, max_retries: int):
        orchestrator = WorkflowOrchestrator(
            self.workflows,
            max_retries=max_retries,
        )

        self.state = await orchestrator.runWorkflows(updateCallback, self.state)
        return self.state

    def display(self):
        try:
            generated_spec = self.state.context["spec_generation_result"]["spec"]
            generated_netlist = self.state.context["netlist_generation_result"]["netlist"]

            # display allat

            print(self.state.current_workflow)
            print(self.state.current_stage)
            print(f"Final Status: {self.state.status}")
            print(
                f"Final Error Message: {'None' if self.state.err_message == '' else self.state.err_message}"
            )
            print(
                f"Total cost of spec gen: ${self.state.workflows_context['spec_generation'].cost:.5f}"
            )
            print(
                f"Total cost of netlist gen: ${self.state.workflows_context['netlist_generation'].cost:.5f}"
            )
            print(
                f"Tokens used by spec gen: {self.state.workflows_context['spec_generation'].total_tokens}"
            )
            print(
                f"Total used by netlist gen: {self.state.workflows_context['netlist_generation'].total_tokens}"
            )
            print(
                "Duration of spec gen:",
                self.state.workflows_context["spec_generation"].duration_ns / (1_000_000),
                "ms",
            )
            print(
                "Duration of netlist gen:",
                self.state.workflows_context["netlist_generation"].duration_ns / (1_000_000),
                "ms",
            )
            # print("GENERATED SPECIFICATION: ")
            # print(generated_spec)
            # print("GENERATED NETLIST: ")
            # print(generated_netlist)
        except Exception as e:
            print(f"Failed to display with exception: {e}")


if __name__ == "__main__":
    spec_workflow = SpecWorkflow()
    netlist_workflow = NetlistWorkflow(tools={"simulate": simulate_tool, "verify": verify_tool})
    circuit_to_printer_workflow = CircuitToPrinterWorkflow()
    workflows = {
        "spec_generation": spec_workflow,
        "netlist_generation": netlist_workflow,
        "circuit_to_printer": circuit_to_printer_workflow,
    }

    state = WorkflowState(
        current_workflow=None,
        context={
            "user_input": "Blink an LED",
            "fail_simulation": False,
            "fail_verification": False,
        },
        memory={},
        current_stage=None,
        status=Status.PENDING,
    )

    executor = Executor(state, workflows)
    first_workflow = list(workflows.keys())[0]
    max_retries = 1

    async def updateCallback(run_type, contents):
        pass

    async def run_and_display():
        new_state = await executor.run(updateCallback, max_retries)
        if new_state.context.get("status") == Status.ERROR:
            print(f"Executor failed with error: {new_state.context.get('err_message')}")
        executor.display()

    asyncio.run(run_and_display())
