from typing import Any, Dict

from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from openai import OpenAIError, RateLimitError

from config import SPEC_GENERATION_PROMPT, USE_MOCK_LLM
from models.BaseModel import BaseModel
from utils.usage import UsageTracker


class SpecAgent:
    def __init__(self, usage_tracker: UsageTracker):
        self.usage_tracker = usage_tracker

    def _mock_spec(self, user_prompt: str) -> dict:
        return {
            "goal": f"Interpret user request: {user_prompt}",
            "inputs": ["5V supply", "1x pushbutton (optional)"],
            "outputs": ["1x LED blinking at ~1 Hz"],
            "constraints": {"max_current_mA": 10, "breadboard_layout": True},
            "notes": ["This is MOCK mode output", "Replace with real LLM later"],
        }

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        user_prompt = state["user_input"]
        tracker = self.usage_tracker

        if USE_MOCK_LLM:
            state["spec"] = self._mock_spec(user_prompt)
            tracker.zeroNode("spec_generation")
            state["usage"]["nodes"]["spec_generation"] = tracker.nodeReport("spec_generation")
            return state

        llm = BaseModel().getModel()
        prompt = PromptTemplate(template=SPEC_GENERATION_PROMPT, input_variables=["user_prompt"])
        parser = JsonOutputParser()
        chain = prompt | llm | parser

        try:
            with tracker.node("spec_generation", provider="openai"):
                spec = chain.invoke({"user_prompt": user_prompt})
            state["spec"] = spec
        except RateLimitError as e:
            state["spec"] = {"error": "OpenAI quota exceeded"}
            tracker.zeroNode("spec_generation")
            state["usage"]["nodes"]["spec_generation"] = tracker.nodeReport("spec_generation")
            print("RateLimitError:", e)
            return state
        except OpenAIError as e:
            state["spec"] = {"error": str(e)}
            tracker.zeroNode("spec_generation")
            state["usage"]["nodes"]["spec_generation"] = tracker.nodeReport("spec_generation")
            print("OpenAI API Error:", e)
            return state

        state["usage"]["nodes"]["spec_generation"] = tracker.nodeReport("spec_generation")
        return state
