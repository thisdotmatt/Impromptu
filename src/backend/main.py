from orchestrator.orchestrator import WorkflowOrchestrator
from utils.usage import UsageTracker
from workflows.NetlistWorkflow import NetlistWorkflow, simulate_tool, verify_tool
from workflows.SpecWorkflow import SpecWorkflow
from config import MAX_RETRIES

tracker = UsageTracker()

spec_workflow = SpecWorkflow(tracker)
netlist_workflow = NetlistWorkflow(tracker, tools=[simulate_tool, verify_tool])

orchestrator = WorkflowOrchestrator(
    workflows=[
        ("spec_generation", lambda *args, **kwargs: spec_workflow.run(*args, **kwargs, max_retries=MAX_RETRIES)),
        ("netlist_pipeline", lambda *args, **kwargs: netlist_workflow.run(*args, **kwargs, max_retries=MAX_RETRIES)),
    ],
    tracker=tracker,
    max_retries=MAX_RETRIES,
)

initial_state = {
    "user_input": "Blink an LED",
    "usage": {"nodes": {}},
    "memory": {},
    "fail_simulation": False,
    "fail_verification": False,
}

# Run
final_state = orchestrator.run_workflows(
    initial_state, on_update=lambda workflow, update: print(workflow, update)
)

# Format the final state in a human-readable way
formatted_final_state = f"""
Final State:
User Input: {final_state['user_input']}

Usage:
- Spec Generation:
  - Prompt Tokens: {final_state['usage']['nodes']['spec_generation']['prompt_tokens']}
  - Completion Tokens: {final_state['usage']['nodes']['spec_generation']['completion_tokens']}
  - Total Tokens: {final_state['usage']['nodes']['spec_generation']['total_tokens']}
  - Total Cost: ${final_state['usage']['nodes']['spec_generation']['total_cost']:.8f}
  - Agent Group: {final_state['usage']['nodes']['spec_generation']['agent_group']}

- Netlist Generation:
  - Prompt Tokens: {final_state['usage']['nodes']['netlist_generation']['prompt_tokens']}
  - Completion Tokens: {final_state['usage']['nodes']['netlist_generation']['completion_tokens']}
  - Total Tokens: {final_state['usage']['nodes']['netlist_generation']['total_tokens']}
  - Total Cost: ${final_state['usage']['nodes']['netlist_generation']['total_cost']:.8f}
  - Agent Group: {final_state['usage']['nodes']['netlist_generation']['agent_group']}

Memory: {final_state['memory']}

Failures:
- Simulation: {final_state['fail_simulation']}
- Verification: {final_state['fail_verification']}

Spec:
- Goal: {final_state['spec']['goal']}
- Inputs: {', '.join(final_state['spec']['inputs'])}
- Outputs: {', '.join(final_state['spec']['outputs'])}
- Constraints:
  - Voltage: {final_state['spec']['constraints']['voltage']}
  - Current: {final_state['spec']['constraints']['current']}
  - Size: {final_state['spec']['constraints']['size']}
- Notes: {final_state['spec']['notes']}

Netlist Attempt: {final_state['netlist_attempt']}

Netlist:\n{final_state['netlist']}

Netlist Status: {final_state['netlist_status']}
"""

print("Final State:", final_state)
print(tracker.formatReport())
print(formatted_final_state)
