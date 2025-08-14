from typing import Any, Dict

from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from openai import OpenAIError, RateLimitError

from config import NETLIST_GENERATION_PROMPT, USE_MOCK_LLM
from models.BaseModel import BaseModel
from utils.usage import UsageTracker


class NetlistAgent:
    def __init__(self, usage_tracker: UsageTracker):
        self.usage_tracker = usage_tracker

    def _mock_netlist(self, specification: str) -> str:
        return (
            f"* MOCK Netlist for: {specification}\nV1 in 0 DC 5\nR1 in out 1k\nC1 out 0 10uF\n.end"
        )

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        specification = state.get("spec") or state.get("user_input", "")
        tracker = self.usage_tracker

        if USE_MOCK_LLM:
            state["netlist"] = self._mock_netlist(specification)
            tracker.zeroNode("netlist_generation")
            state["usage"]["nodes"]["netlist_generation"] = tracker.nodeReport("netlist_generation")
            return state

        llm = BaseModel().getModel()
        prompt = PromptTemplate(
            template=NETLIST_GENERATION_PROMPT, input_variables=["specification"]
        )
        parser = StrOutputParser()
        chain = prompt | llm | parser

        try:
            with tracker.node("netlist_generation", provider="openai"):
                netlist_text = chain.invoke({"specification": specification})
            state["netlist"] = netlist_text
        except RateLimitError as e:
            state["netlist"] = {"error": "OpenAI quota exceeded"}
            tracker.zeroNode("netlist_generation")
            state["usage"]["nodes"]["netlist_generation"] = tracker.nodeReport("netlist_generation")
            print("RateLimitError:", e)
            return state
        except OpenAIError as e:
            state["netlist"] = {"error": str(e)}
            tracker.zeroNode("netlist_generation")
            state["usage"]["nodes"]["netlist_generation"] = tracker.nodeReport("netlist_generation")
            print("OpenAI API Error:", e)
            return state

        state["usage"]["nodes"]["netlist_generation"] = tracker.nodeReport("netlist_generation")
        return state
