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

USE_MOCK_LLM = True