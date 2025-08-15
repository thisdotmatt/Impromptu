
from typing import Any, Dict
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from openai import OpenAIError, RateLimitError
from config import NETLIST_GENERATION_PROMPT, USE_MOCK_LLM
from models.OpenAIModel import OpenAIModel
from agents.BaseAgent import BaseAgent

class NetlistAgent(BaseAgent):
    '''
    Takes in a pre-defined electrical specification and converts this into a netlist.
    The generated netlist is NOT verified - this agent is strictly for generation.
    We use open source tools and similar to verify the functionality of the netlist
    and retry if necessary. See src/backend/workflows/NetlistWorkflow.py 
    '''
    def _mock(self, prompt: str) -> str:
        return (
            f"* MOCK Netlist for: {prompt}\nV1 in 0 DC 5\nR1 in out 1k\nC1 out 0 10uF\n.end"
        )

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        specification = state.get("spec") or state.get("user_input", "")
        tracker = self.usage_tracker

        if USE_MOCK_LLM:
            state["netlist"] = self._mock(specification)
            tracker.initializeTokenReportForAgent("netlist_generation") # we don't actually track token/cost for mocked responses
            state["usage"]["nodes"]["netlist_generation"] = tracker.getTokenReportForAgent("netlist_generation")
            return state

        # sets up the LLM pipeline
        # we create a prompt template with the prompt and whatever input variables 
        # we'd like to add in (e.g. context). Then we pass the result to our LLM, and then
        # parse the generated text in JSON format
        llm = OpenAIModel().getModel()
        prompt = PromptTemplate(
            template=NETLIST_GENERATION_PROMPT, input_variables=["specification"]
        )
        parser = StrOutputParser()
        chain = prompt | llm | parser

        try:
            with tracker.agent("netlist_generation", provider="openai"):
                netlist_text = chain.invoke({"specification": specification})
            state["netlist"] = netlist_text
        except RateLimitError as e:
            state["netlist"] = {"error": "OpenAI quota exceeded"}
            tracker.initializeTokenReportForAgent("netlist_generation")
            state["usage"]["nodes"]["netlist_generation"] = tracker.getTokenReportForAgent("netlist_generation")
            print("RateLimitError:", e)
            return state
        except OpenAIError as e:
            state["netlist"] = {"error": str(e)}
            tracker.initializeTokenReportForAgent("netlist_generation")
            state["usage"]["nodes"]["netlist_generation"] = tracker.getTokenReportForAgent("netlist_generation")
            print("OpenAI API Error:", e)
            return state
        
        # for all other exceptions, we generally want the program to end "loudly" so that we can fix the bug

        state["usage"]["nodes"]["netlist_generation"] = tracker.getTokenReportForAgent("netlist_generation")
        return state
