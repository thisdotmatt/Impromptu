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
