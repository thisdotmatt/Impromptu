MAX_RUN_COST = 0.001  # in USD
MAX_RETRIES = 1
USE_MOCK_LLM = True

components = """
NE555 x4
LED x20
1 MOhm Resistor x5
5K Ohm Resistor x50
1K Ohm Resistor x10
500 Ohm Resistor x50
470 Ohm Resistor x100
100 Ohm Resistor x50
10 Ohm Resistor x100
1uF Capacitor x20
50pF Capacitor x20
1nF Capacitor x20
5nF Capacitor x10
5V Voltage Source with GND connection available x1
"""


SPEC_GENERATION_PROMPT = """
You are an assistant that extracts structured circuit specifications from user requests.

The following represent the available components that may or may not be used in the design: {components}

Given the user's prompt, return a JSON object with:
- goal: high-level purpose of the circuit
- inputs: list of input signals/components
- outputs: list of output signals/components
- constraints: any voltage, current, or size limitations
- notes: additional relevant details

User prompt: {user_prompt}
"""

NETLIST_GENERATION_PROMPT = """
You are an expert electronics designer. Generate a valid SPICE netlist for the following circuit specification:

The following represent the available components that may or may not be used in the design: {components}

Specification:
{specification}

Guidelines:
- Output only the SPICE netlist in plain text (no explanations, no code fences).
- Ensure the netlist is compatible with Ngspice / PySpice.
- Include all necessary component values, models, and connections.
- If the circuit requires a power source, define it explicitly.
- Use standard node naming (0 for ground).
- Assume standard component models unless otherwise stated.

Output format:
<valid SPICE netlist>
"""

CHAT_SYSTEM_PROMPT = """
You are a senior electrical engineer. You give very brief, direct responses, and ask questions that help your customers identify their business needs. 
Allow the customer to take the lead and explain what they want - only step in if they have questions or if you need clarification.
If you find the customer doesn't really seem to need your help, be willing to ask for further questions and if they have none, stop.
"""

MOCK_GCODE = """
; Impromptu Circuit Board G-code
; Generated for pick-and-place machine
; Board: Circuit Design v1.0
; Components: 24 total

G21 ; Set units to millimeters
G90 ; Absolute positioning
M84 S0 ; Disable motor idle timeout

; Component placement sequence
G0 X10.5 Y15.2 ; Move to R1 position
M3 S1000 ; Pick component
G0 X10.5 Y15.2 Z-2 ; Place component
M5 ; Release component

G0 X25.3 Y20.1 ; Move to C1 position
M3 S1000 ; Pick component
G0 X25.3 Y20.1 Z-2 ; Place component
M5 ; Release component

; Additional components...
; Total placement time: ~3.2 minutes

M30 ; Program end
"""
