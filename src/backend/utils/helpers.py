import json
from typing import Tuple
from ltspice import Ltspice


def formatSSEMessage(event) -> str:
    return f"data: {json.dumps(event)}\n\n"

async def checkTracesUnderMaxCurrent(spiceObj: Ltspice, max_current: float = 3.0) -> Tuple[bool, str | None, float | None]:
    # good way to determine whether a given netlist has a short circuit
    # returns a list of:
    # 1. Boolean of whether there was a violating trace
    # 2. the problem trace identifier (e.g. I(n001))
    # 3. the violating current
    print(f"Variables: {spiceObj.variables}")
    for trace in spiceObj.variables:
        if trace.startswith("I"): # is current
            current_elem = spiceObj.get_data(name=trace)
            max_curr = abs(current_elem.max())  
            if max_curr > max_current:
                return (False, trace, max_curr)
    return (True, None, None)

async def checkTracesUnderMaxVoltage(spiceObj: Ltspice, max_voltage: float = 20.0) -> Tuple[bool, str | None, float | None]:
    # good way to determine whether a given netlist has exceeded the voltage specified by the system
    # returns a list of:
    # 1. Boolean of whether there was a violating trace
    # 2. the problem trace identifier (e.g. V(n001))
    # 3. the violating voltage
    for trace in spiceObj.variables:
        if trace.startswith("V"): # is current
            current_elem = spiceObj.get_data(name=trace)
            max_vol = abs(current_elem.max())  
            if max_vol > max_voltage:
                return (False, trace, max_vol)
    return (True, None, None)