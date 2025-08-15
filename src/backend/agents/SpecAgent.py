from typing import Any, Dict
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from openai import OpenAIError, RateLimitError
from config import SPEC_GENERATION_PROMPT, USE_MOCK_LLM
from models.OpenAIModel import OpenAIModel
from agents.BaseAgent import BaseAgent

class SpecAgent(BaseAgent):
    '''
    Generates a detailed JSON specification for a planned circuit given
    a high-level overview of the user's business needs.
    '''
    def _mock(self, prompt: str) -> dict:
        return {
            "goal": f"Interpret user request: {prompt}",
            "inputs": ["5V supply", "1x pushbutton (optional)"],
            "outputs": ["1x LED blinking at ~1 Hz"],
            "constraints": {"max_current_mA": 10, "breadboard_layout": True},
            "notes": ["This is MOCK mode output", "Replace with real LLM later"],
        }

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        user_prompt = state["user_input"]
        tracker = self.usage_tracker

        if USE_MOCK_LLM:
            state["spec"] = self._mock(user_prompt)
            tracker.initializeTokenReportForAgent("spec_generation")
            state["usage"]["nodes"]["spec_generation"] = tracker.getTokenReportForAgent("spec_generation")
            return state

        # sets up the LLM pipeline
        # we create a prompt template with the prompt and whatever input variables 
        # we'd like to add in (e.g. context). Then we pass the result to our LLM, and then
        # parse the generated text in JSON format
        llm = OpenAIModel().getModel()
        prompt = PromptTemplate(template=SPEC_GENERATION_PROMPT, input_variables=["user_prompt"])
        parser = JsonOutputParser()
        chain = prompt | llm | parser

        try:
            with tracker.agent("spec_generation", provider="openai"):
                spec = chain.invoke({"user_prompt": user_prompt})
            state["spec"] = spec
        except RateLimitError as e: # ask matt to buy more OpenAI credits
            state["spec"] = {"error": "OpenAI quota exceeded"}
            tracker.initializeTokenReportForAgent("spec_generation")
            state["usage"]["nodes"]["spec_generation"] = tracker.getTokenReportForAgent("spec_generation")
            print("RateLimitError:", e)
            return state
        except OpenAIError as e: # something's usually wrong on OpenAI's side or the model is broken
            state["spec"] = {"error": str(e)}
            tracker.initializeTokenReportForAgent("spec_generation")
            state["usage"]["nodes"]["spec_generation"] = tracker.getTokenReportForAgent("spec_generation")
            print("OpenAI API Error:", e)
            return state
        
        # for all other exceptions, we generally want the program to end "loudly" so that we can fix the bug

        state["usage"]["nodes"]["spec_generation"] = tracker.getTokenReportForAgent("spec_generation")
        return state
