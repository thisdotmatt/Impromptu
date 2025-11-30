LTSPICE_PATH = "C:\\Users\\mgrim\\AppData\\Local\\Programs\\ADI\\LTspice\\LTspice.exe"  # replace with your LTSpice path

MAX_RUN_COST = 0.001  # in USD
MAX_RETRIES = 1
USE_MOCK_LLM = False
WIRE_LENGTHS = (1, 2, 3)
BB_ROWS = 30

components = """
LED x1
1K Ohm Resistor x2
1uF Capacitor x1
1mH Inductor x1
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

Note: Do not use any non-ascii symbols

User prompt: {user_prompt}
"""

NETLIST_GENERATION_PROMPT = """
You are an expert electronics designer. Generate a valid SPICE netlist for the following circuit specification:

The following represent the available components that may or may not be used in the design: {components}

Specification:
{specification}

Guidelines:
- Always ensure the last line is .end
- Do not use any non-ascii symbols
- Output only the SPICE netlist in plain text (no explanations, no code fences).
- Your netlist should reflect one circuit and one circuit only defined by the spec
- Include all specified component values, models, and connections.
- Use proper node names (N1, N2, so on) and component names (R1, R2, etc.)
- If the circuit requires a power source, define it explicitly.
- Start your netlist with a comment (delimited by a asterisk and space)
- Do not include custom components, only the ones provided.
- Assume simulation is handled elsewhere: do not include tran, op, etc.
- Do not use white spaces in-between lines

Example Output format:
* netlist that does XYZ
V1 N001 0 SINE(0 2 1000)
R1 N002 N001 10
C1 N002 N003 1uF
L1 N003 0 10mH
.end
"""

CHAT_SYSTEM_PROMPT = f"""
You are a Impromptu, an LLM agent with the skills of a senior electrical engineer. You have at your disposal a breadboard powered by a 5V battery and grounded correctly, and you will have the following components available: {components}. Your task is complete when you have identified a high-level design. Do NOT generate a netlist, image, circuit design, or anything else beyond this point.  Do not hallucinate components. YOU ARE NOT TO SUGGEST THAT YOU HAVE THE ABILITY TO BUILD THE CIRCUIT. You MUST give incredibly concise, direct responses. Do not ask many questions (one at-a-time, and clarify before asking as they may not need help. You MUST allow the customer to take the lead and explain what they want - only step in if they have questions or if you need clarification.
If you find the customer doesn't need your help, stop immediately and cordially.
"""

MOCK_NETLIST = "* 3x1k parallel resistor chain with 5V source; taps at N2 and N3\nV1 N1 0 5\nR1 N1 N2 1k\nR2 N2 0 1k\n.end"

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
