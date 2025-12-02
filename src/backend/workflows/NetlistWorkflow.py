import os
from datetime import datetime, timezone
from typing import Awaitable, Dict, List

import ltspice
from agents.NetlistAgent import NetlistAgent
from config import LTSPICE_PATH, USE_MOCK_LLM
from spicelib import SimRunner, SpiceEditor
from spicelib.simulators.ltspice_simulator import LTspice
from utils.helpers import validateNetlist
from utils.types import EventCallback, Status, WorkflowState
from workflows.BaseWorkflow import BaseWorkflow


class NetlistWorkflow(BaseWorkflow):
    """
    Workflow for generating a netlist from an engineering specification and verifying it using external tools
    """

    def __init__(self, tools: Dict[str, List[Awaitable]] = None):
        self.agent = NetlistAgent()
        self.tools = tools

    async def run(
        self, state: WorkflowState, updateCallback: EventCallback, max_retries: int = 1
    ) -> WorkflowState:
        if state.context.get("spec_generation_result") == None:
            state.status = Status.ERROR
            state.err_message = f"Error during workflow {state.current_workflow}: missing 'spec' field in state.context"
            return state

        workflow_name = state.current_workflow or "netlist_generation"

        attempt = 0
        while attempt < max_retries:
            attempt += 1

            step_index = 0

            # generate stage
            state.current_stage = "generate"
            state.status = Status.RUNNING
            step_index += 1
            await updateCallback(
                "substage_started",
                {
                    "type": "substage_started",
                    "workflow": workflow_name,
                    "substage": state.current_stage,
                    "step_index": step_index,
                    "ts": datetime.now(timezone.utc).isoformat(),
                },
            )

            prompt = state.context.get("spec_generation_result")
            model = state.memory.get("selected_model")
            agent_response = await self.agent.run(model=model, prompt=prompt)
            if agent_response.status == Status.ERROR:
                state.status = Status.ERROR
                state.err_message = f"Error during workflow {state.current_workflow} while executing agent: {agent_response.err_message}"
                return state

            result_name = f"{workflow_name}_result"
            state.context[result_name] = {"netlist": agent_response.response}

            # generate completed
            await updateCallback(
                "substage_completed",
                {
                    "type": "substage_completed",
                    "workflow": workflow_name,
                    "substage": state.current_stage,
                    "step_index": step_index,
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "meta": {},
                },
            )

            # run the tools to verify the netlist is correct
            all_tools_passed = True
            hasTools = self.tools is not None and len(list(self.tools.keys())) != 0
            if hasTools:
                for tool_name in self.tools:
                    # tool stage
                    state.current_stage = tool_name
                    state.status = Status.RUNNING
                    step_index += 1
                    await updateCallback(
                        "substage_started",
                        {
                            "type": "substage_started",
                            "workflow": workflow_name,
                            "substage": state.current_stage,
                            "step_index": step_index,
                            "ts": datetime.now(timezone.utc).isoformat(),
                        },
                    )

                    state = await self.tools[tool_name](state)

                    if state.status == Status.ERROR:
                        all_tools_passed = False
                        break

                    await updateCallback(
                        "substage_completed",
                        {
                            "type": "substage_completed",
                            "workflow": workflow_name,
                            "substage": state.current_stage,
                            "step_index": step_index,
                            "ts": datetime.now(timezone.utc).isoformat(),
                            "meta": {},
                        },
                    )

            if all_tools_passed:  # else retry/fail
                state.status = Status.SUCCESS
                return state

        state.status = Status.ERROR
        state.err_message = f"Error during workflow {state.current_workflow} while running stage {state.current_stage}: {state.err_message}"
        return state


async def simulate_tool(state: WorkflowState):
    if USE_MOCK_LLM:
        return
    try:
        result_key = f"{state.current_workflow}_result"
        netlist_str = state.context.get(result_key, {}).get("netlist")

        if not netlist_str:
            raise ValueError("Missing generated netlist in context")

        output_dir = ".\\spice_runs"
        os.makedirs(output_dir, exist_ok=True)
        netlist_path = os.path.join(output_dir, "current_netlist.net")
        print("Writing netlist to path: ", netlist_path)
        with open(netlist_path, "w") as f:
            f.write(netlist_str)

        editor = SpiceEditor(netlist_path, create_blank=False)

        with open(netlist_path, "r") as f:
            line = f.readline()
            while line != "" and line != ".end":
                print("read line: ", line)
                editor.add_instruction(line)
                line = f.readline()
        # editor.add_instruction(".tran 0 0.1 0 0.01")
        editor.add_instruction(".op")  # temporary, add more intelligent simulation later
        editor.add_instruction(".backanno")
        # print("Components: ", editor.get_components())
        # print(f"Netlist: {editor.netlist}")
        print(editor.netlist)
        runner = SimRunner(
            simulator=LTspice.create_from(LTSPICE_PATH),
            verbose=True,
            output_folder=output_dir,
        )
        print("Got to just before run_now")
        raw_path, log_path = runner.run_now(
            netlist=editor, exe_log=True, run_filename="generated_run.net"
        )

        state.context["simulation_result"] = {
            "raw_path": raw_path,
            "log_path": log_path,
            "okSim": runner.okSim,
            "runno": runner.runno,
        }
        if runner.okSim == 0:
            raise RuntimeError("LTSpice simulation failed or produced no valid runs")

        state.status = Status.SUCCESS

    except Exception as e:
        state.status = Status.ERROR
        workflow_name = state.current_workflow or "netlist_generation"
        result_name = f"{workflow_name}_result"
        state.err_message = (
            f"Simulation failed: Generated Netlist:\n {state.context[result_name]}\nError:\n {e}"
        )

    return state


async def verify_tool(state: WorkflowState):
    if USE_MOCK_LLM:
        return
    try:
        sim_result = state.context.get("simulation_result", {})
        raw_path = sim_result.get("raw_path")

        if not raw_path or not os.path.exists(raw_path):
            raise FileNotFoundError("Missing or invalid LTSpice .raw file")

        l = ltspice.Ltspice(raw_path)
        l.parse()

        validation = await validateNetlist(spiceObj=l)

        if not (validation["short_ok"] and validation["voltage_ok"]):
            state.status = Status.ERROR
            state.err_message = "; ".join(validation["problems"])
        else:
            state.context["verification_result"] = validation
            state.status = Status.SUCCESS

    except Exception as e:
        state.status = Status.ERROR
        state.err_message = f"Verification failed: {e}"

    return state
