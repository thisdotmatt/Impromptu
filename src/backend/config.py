SPEC_GENERATION_PROMPT = """
You are an assistant that extracts structured circuit specifications from user requests.

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

MAX_RUN_COST = 0.001
MAX_RETRIES = 1
USE_MOCK_LLM = True
