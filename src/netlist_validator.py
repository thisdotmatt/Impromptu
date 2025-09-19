from spicelib import SpiceEditor, SimRunner
from spicelib.simulators.ltspice_simulator import LTspice
from spicelib.log.ltsteps import LTSpiceLogReader
from spicelib import RawRead
import ltspice
from ltspice import Ltspice
import matplotlib.pyplot as plt
import numpy as np
import os
from typing import Tuple
from backend.utils.helpers import checkTracesUnderMaxCurrent, checkTracesUnderMaxVoltage
import asyncio

editor = SpiceEditor("rc_test.net", create_blank=True)
ltspice_path = "C:\\Users\\mgrim\\AppData\\Local\\Programs\\ADI\\LTspice\\LTspice.exe" # replace with your LTSpice path
netlist_path = ".\\test_short.net"

with open(netlist_path, "r") as f:
    line = f.readline()
    while line != "" and line != ".end":
        print("read line: ", line)
        editor.add_instruction(line)
        line = f.readline()

editor.add_instruction(".tran 0 0.1 0 0.01")
editor.add_instruction(".op")
editor.add_instruction(".backanno")
editor.add_instruction(".end")

print(f"Netlist: {editor.netlist}")

runner = SimRunner(simulator=LTspice.create_from(ltspice_path), verbose=True, output_folder="./spice_runs")
raw_path, log_path = runner.run_now(netlist=editor, exe_log=True, run_filename="rc_run.net")
print("RAW:", raw_path, "LOG:", log_path)
print(runner.sim_info())

if log_path:
    log = LTSpiceLogReader(log_path)
    print(f"Dataset: {log.dataset}")
    print("Number of steps in log:", getattr(log, "step_count", None))

print('Successful/Total Simulations: ' + str(runner.okSim) + '/' + str(runner.runno))
traces = None
try:
    raw_read = RawRead(raw_filename=raw_path, dialect="ltspice", verbose=True)
    print(f"Encoding: {raw_read.encoding}")
    traces = raw_read.get_trace_names()
    print(f"Traces: {traces}")
    df = raw_read.export()
    print(f"Struct as df: {df.keys()}")
except Exception as e:
    print(f"Caught exception when reading raw file: {e}\n")

l = ltspice.Ltspice(raw_path) 
l.parse() 

time = l.get_time()
V_source = l.get_data(name='V(n001)')
V_cap = l.get_data(name='V(n003)')
    
async def validateNetlist():
    short_check, problem_trace, problem_current = await checkTracesUnderMaxCurrent(spiceObj = l)
    if not short_check:
        print(f"ERROR with trace {problem_trace}: short circuit with current {problem_current}")
    else:
        print("No sign of short circuit")
    voltage_check, problem_trace, problem_voltage = await checkTracesUnderMaxVoltage(spiceObj = l)
    if not voltage_check:
        print(f"ERROR with trace {problem_trace}: very high voltage of {problem_voltage}")
    else:
        print("No sign of high voltage")
        
    if short_check and voltage_check:
        # display allat
        plt.xlim((0, 0.01))
        plt.ylim((-2, 2))
        plt.plot(time, V_source)
        plt.plot(time, V_cap)
        plt.show()

asyncio.run(validateNetlist())

runner.cleanup_files()