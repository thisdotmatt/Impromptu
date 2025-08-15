from orchestrator.orchestrator import WorkflowOrchestrator
from utils.types import Status, WorkflowState
from workflows.ManufacturingWorkflow import ManufacturingWorkflow
from workflows.NetlistWorkflow import NetlistWorkflow, simulate_tool, verify_tool
from workflows.SpecWorkflow import SpecWorkflow

spec_workflow = SpecWorkflow()
netlist_workflow = NetlistWorkflow(tools={"simulate": simulate_tool, "verify": verify_tool})
manufacturing_workflow = ManufacturingWorkflow()

orchestrator = WorkflowOrchestrator(
    workflows={
        "spec_generation": spec_workflow.run,
        "netlist_generation": netlist_workflow.run,
        "manufacturing": manufacturing_workflow.run,
    },
    max_retries=1,
)

workflow_state = WorkflowState(
    current_workflow=None,
    context={"user_input": "Blink an LED", "fail_simulation": False, "fail_verification": False},
    memory={},
    current_stage=None,
    status=Status.PENDING,
)

final_states = orchestrator.runWorkflows(workflow_state)

generated_spec = workflow_state.context["spec"]
generated_netlist = workflow_state.context["netlist"]

# display allat

print(workflow_state.current_workflow)
print(workflow_state.current_stage)
print(workflow_state.status)
print(workflow_state.err_message)
print(f"Total cost of spec gen: ${workflow_state.workflows_context['spec_generation'].cost:.5f}")
print(
    f"Total cost of netlist gen: ${workflow_state.workflows_context['netlist_generation'].cost:.5f}"
)
print(
    f"Tokens used by spec gen: {workflow_state.workflows_context['spec_generation'].total_tokens}"
)
print(
    f"Total used by netlist gen: {workflow_state.workflows_context['netlist_generation'].total_tokens}"
)
print(
    "Duration of spec gen:",
    workflow_state.workflows_context["spec_generation"].duration_ns / (1_000_000),
    "ms",
)
print(
    "Duration of netlist gen:",
    workflow_state.workflows_context["netlist_generation"].duration_ns / (1_000_000),
    "ms",
)
print("GENERATED SPECIFICATION: ")
print(generated_spec)
print("GENERATED NETLIST: ")
print(generated_netlist)
