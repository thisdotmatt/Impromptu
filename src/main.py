from utils.usage import UsageTracker
from orchestrator.orchestrator import WorkflowOrchestrator
from workflows.SpecWorkflow import SpecWorkflow
from workflows.NetlistWorkflow import NetlistWorkflow, simulate_tool, verify_tool

tracker = UsageTracker()

spec_workflow = SpecWorkflow(tracker)
netlist_workflow = NetlistWorkflow(tracker, tools=[simulate_tool, verify_tool], max_retries=1)

orchestrator = WorkflowOrchestrator(
    workflows=[
        ("spec_generation", spec_workflow.run),
        ("netlist_pipeline", netlist_workflow.run)
    ],
    tracker=tracker,
    max_retries=1
)

initial_state = {
    "user_input": "Blink an LED",
    "usage": {"nodes": {}},
    "memory": {},
    "fail_simulation": False,
    "fail_verification": False
}

# Run
final_state = orchestrator.run_workflows(
    initial_state,
    on_update=lambda workflow, update: print(workflow, update)
)

print("Final State:", final_state)
print(tracker.formatReport())
