import asyncio
import os
from datetime import datetime, timezone
from typing import Dict, List, Tuple

import requests
from spicelib import SpiceEditor
from utils.helpers import (
    Breadboard,
    Dbg,
    Net,
    Passive,
    PnR,
    generate_gcode_from_solution,
    renderBreadboard,
)
from utils.types import EventCallback, Status, WorkflowState
from workflows.BaseWorkflow import BaseWorkflow
from config import WIRE_LENGTHS, BB_ROWS

# Printer IP for G-code execution
MOONRAKER_URL = "http://10.3.141.1/printer/gcode/script"

COMPONENT_DEFAULTS = {
    "R": {"length": 3, "orientation": "v"},
    "C": {"length": 3, "orientation": "v"},
    "L": {"length": 3, "orientation": "v"},
    "D": {"length": 3, "orientation": "v"},
    "LED": {"length": 3, "orientation": "v"},
}


def _parse_models_and_instances(netlist_path: str) -> Tuple[set, Dict[str, str]]:
    """
    Light-weight text parse to:
      - collect diode model names that look like LEDs (model name contains 'LED')
      - map diode instance -> model name
    """
    led_models = set()
    diode_inst_to_model: Dict[str, str] = {}

    with open(netlist_path, "r") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("*"):
                continue

            low = line.lower()

            # .model DLED D ( ... )
            if low.startswith(".model"):
                toks = line.split()
                if len(toks) >= 3:
                    model_name = toks[1]
                    model_kind = toks[2].upper()
                    # Treat diode models whose names contain 'LED' as LED footprints
                    if model_kind.startswith("D") and ("LED" in model_name.upper()):
                        led_models.add(model_name)

            # D1 n+ n- MODEL ...
            elif line[0].upper() == "D":
                toks = line.split()
                if len(toks) >= 4:
                    ref = toks[0]
                    model = toks[3]
                    diode_inst_to_model[ref] = model

    return led_models, diode_inst_to_model


def _detect_single_supply(editor: SpiceEditor) -> str:
    """
    Returns the net name that should be treated as V+ (if any).
    We look for a voltage source whose negative terminal is '0' (ground).
    """
    vplus = None
    for ref in editor.get_components():
        if ref.upper().startswith(("V",)):
            try:
                nodes = editor.get_component_nodes(ref)
            except Exception:
                continue
            if len(nodes) >= 2:
                pos, neg = nodes[0], nodes[1]
                if neg == "0":
                    vplus = pos
                    break
    return vplus


def _node_alias_fn(vplus_net: str):
    """
    Returns a function that maps raw SPICE nets → ('V+', 'GND', or raw intermediate).
    """

    def alias(n: str) -> str:
        if n == "0" or n.upper() == "GND":
            return "GND"
        if vplus_net and n == vplus_net:
            return "V+"
        return n

    return alias


def _compact_internal_nets(bindings_raw: Dict[str, Tuple[str, str]]) -> Dict[str, Tuple[str, str]]:
    """
    Renames all non-rail nets to N1, N2, ... to match breadboard expectations.
    """
    mapping: Dict[str, str] = {}
    next_idx = 1

    def rename(n: str) -> str:
        nonlocal next_idx
        if n in ("V+", "GND"):
            return n
        if n not in mapping:
            mapping[n] = f"N{next_idx}"
            next_idx += 1
        return mapping[n]

    bindings: Dict[str, Tuple[str, str]] = {}
    for k, (a, b) in bindings_raw.items():
        bindings[k] = (rename(a), rename(b))

    print("Renamed nets:", mapping)
    return bindings


def _make_passives_from_names(part_names: List[str]) -> List[Passive]:
    """
    Create Passive objects with defaults, interpreting names like 'LED' specially.
    """
    comps: List[Passive] = []
    for name in part_names:
        # Choose defaults key
        key = "".join([c for c in name if not c.isdigit()]).upper()
        if key.startswith("LED"):
            key = "LED"
        elif key:  # take first letter for generic families like R, C, L, D
            key = key[0]
        else:
            key = "R"

        meta = COMPONENT_DEFAULTS.get(key, {"length": 3, "orientation": "v"})
        comps.append(Passive(name, length=meta["length"], orientation=meta["orientation"]))
    return comps


def netlist_to_pnr_inputs(netlist_path: str):
    """
    Core translation:
      SPICE netlist  →  (nets: Dict[str, Net], comps: List[Passive], bindings: Dict[str, (n1,n2)])
    Rules:
      - detect single-supply V+ (positive of any V* tied to '0')
      - GND := '0'
      - passives = R*, C*, L*, D* (diodes with LED model become 'LED', others remain 'D#')
      - skip sources (V*/I*)
      - compact internal nets to N1, N2, ...
    """
    if not os.path.exists(netlist_path):
        raise FileNotFoundError(f"Netlist not found at {netlist_path}")

    editor = SpiceEditor(netlist_path)

    # Identify rails
    vplus_net = _detect_single_supply(editor)
    print(f"[DEBUG] Detected V+ net: {vplus_net}")
    alias = _node_alias_fn(vplus_net)

    # LED detection (simple heuristic via .model name)
    led_models, diode_inst_to_model = _parse_models_and_instances(netlist_path)
    print(f"[DEBUG] LED models: {led_models}, Diode instances: {diode_inst_to_model}")

    entries = []  # list of (base_name, a, b)
    for ref in editor.get_components():
        uref = ref.upper()
        if uref.startswith(("V", "I")):
            continue
        try:
            nodes = editor.get_component_nodes(ref)
        except Exception as e:
            print(f"[DEBUG] Failed to get nodes for {ref}: {e}")
            continue
        if len(nodes) < 2:
            continue

        a, b = alias(nodes[0]), alias(nodes[1])

        # If diode with LED model, use 'LED' as base label; else keep reference name
        base = ref
        if uref.startswith("D"):
            model = diode_inst_to_model.get(ref, "")
            if model and (model in led_models or "LED" in model.upper()):
                base = "LED"

        entries.append((base, a, b))
        print(f"[DEBUG] Entry: {ref} -> {base}: {a} -> {b}")

    # Compact internal nets to N1, N2, ...
    def _compact(n):
        if n in ("V+", "GND"):
            return n
        if n not in mapping:
            mapping[n] = f"N{len(mapping) + 1}"
        return mapping[n]

    mapping = {}
    compacted_entries = [(base, _compact(a), _compact(b)) for base, a, b in entries]
    print("[DEBUG] Renamed nets:", mapping)

    # Disambiguate names and build final component list
    name_counts = {}
    final_names = []
    final_bindings = {}

    for base, a, b in compacted_entries:
        idx = name_counts.get(base, 0)
        name_counts[base] = idx + 1
        name = base if idx == 0 else f"{base}{idx}"
        final_names.append(name)
        final_bindings[name] = (a, b)

    # Create Passives
    comps = _make_passives_from_names(final_names)
    print(f"[DEBUG] Created {len(comps)} components: {[c.name for c in comps]}")

    # Build nets dict for internal nets only
    internal = set()
    for a, b in final_bindings.values():
        if a not in ("V+", "GND"):
            internal.add(a)
        if b not in ("V+", "GND"):
            internal.add(b)
    nets = {n: Net(n) for n in sorted(internal)}
    print(f"[DEBUG] Created {len(nets)} internal nets: {list(nets.keys())}")

    # Debug prints
    try:
        print("[DEBUG] Components (final):", final_names)
        print("[DEBUG] Bindings (component-level):", final_bindings)
        print("[DEBUG] Internal nets:", list(nets.keys()))
    except Exception:
        pass

    # Return component-level bindings directly
    return nets, comps, final_bindings


def execute_gcode(gcode_content: str) -> bool:
    """
    Execute G-code commands on the printer via Moonraker API.

    Args:
        gcode_content: String containing G-code commands

    Returns:
        True if successful, False otherwise
    """
    try:
        payload = {"script": gcode_content}
        response = requests.post(MOONRAKER_URL, json=payload, timeout=30)

        if response.status_code == 200:
            print(f"[SUCCESS] G-code executed: {len(gcode_content)} bytes sent")
            return True
        else:
            print(f"[ERROR] Moonraker returned {response.status_code}: {response.text}")
            return False

    except requests.exceptions.Timeout:
        print("[ERROR] Moonraker request timed out")
        return False
    except requests.exceptions.ConnectionError:
        print("[ERROR] Failed to connect to Moonraker at {}".format(MOONRAKER_URL))
        return False
    except Exception as e:
        print(f"[ERROR] G-code execution failed: {e}")
        return False


class CircuitToPrinterWorkflow(BaseWorkflow):
    async def run(self, state: WorkflowState, updateCallback: EventCallback) -> WorkflowState:
        workflow_name = state.current_workflow or "circuit_to_printer"
        state.status = Status.RUNNING

        await updateCallback(
            "substage_started",
            {
                "type": "substage_started",
                "workflow": workflow_name,
                "substage": "circuit_to_printer",
                "step_index": 1,
                "ts": datetime.now(timezone.utc).isoformat(),
            },
        )

        try:
            netlist_info = state.context.get("netlist_generation_result")
            if not netlist_info or "netlist" not in netlist_info:
                raise ValueError("Missing netlist in context for CircuitToPrinterWorkflow")

            # Persist the netlist for parsing
            netlist_str = netlist_info["netlist"]
            out_dir = "./spice_runs"
            os.makedirs(out_dir, exist_ok=True)
            netlist_path = os.path.join(out_dir, "current_netlist.net")
            with open(netlist_path, "w") as f:
                f.write(netlist_str)
            print(f"[DEBUG] Netlist saved to {netlist_path}")

            # Convert SPICE → PnR inputs
            print("[DEBUG] Converting netlist to PnR inputs...")
            nets, comps, bindings = netlist_to_pnr_inputs(netlist_path)
            print(f"[DEBUG] PnR inputs ready: {len(comps)} comps, {len(nets)} nets")

            # Breadboard & PnR
            print("[DEBUG] Initializing Breadboard...")
            dbg = Dbg(on=True, logfile="pnr_debug.log")  # Enable debugging
            bb = Breadboard(rows=BB_ROWS, wire_lengths=WIRE_LENGTHS)
            print(
                f"[DEBUG] Breadboard created: {len(bb.holes)} holes, {len(bb.rails_v)} V+ rails, {len(bb.rails_g)} GND rails"
            )

            print("[DEBUG] Initializing PnR...")
            pnr = PnR(bb, nets, comps, dbg=dbg)

            print(f"[DEBUG] Starting place_and_route with bindings: {bindings}")
            ok = pnr.place_and_route(bindings)
            print(f"[DEBUG] place_and_route returned: {ok}")

            if not ok:
                state.context["status"] = Status.ERROR
                state.context["err_message"] = "P&R failed"
                state.status = Status.ERROR
                return state

            sol = pnr.solution()
            #print(f"[DEBUG] Solution: {sol}")

            # Generate real G-code from PnR solution
            print("[DEBUG] Generating G-code from PnR solution...")
            gcode_output = generate_gcode_from_solution(sol)
            print(f"[DEBUG] G-code generated successfully ({len(gcode_output)} bytes)")

            breadboard_image_b64 = renderBreadboard(sol, bb, filename=None, show=False)

            # Store results
            result_name = f"{workflow_name}_result"
            state.context[result_name] = {
                "routing": "P&R completed successfully",
                "gcode": gcode_output,
                "breadboard_image": breadboard_image_b64,
            }
            state.status = Status.SUCCESS
            print("[DEBUG] Workflow completed successfully")

        except Exception as e:
            print(f"[ERROR] CircuitToPrinter failed: {e}")
            state.context["status"] = Status.ERROR
            state.context["err_message"] = str(e)
            state.status = Status.ERROR

        await asyncio.sleep(1) 

        await updateCallback(
            "substage_completed",
            {
                "type": "substage_completed",
                "workflow": workflow_name,
                "substage": "circuit_to_printer",
                "step_index": 1,
                "ts": datetime.now(timezone.utc).isoformat(),
                "meta": {},
            },
        )
        return state
