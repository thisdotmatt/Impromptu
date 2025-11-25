import asyncio

from agents.BaseAgent import BaseAgent
from config import SPEC_GENERATION_PROMPT, USE_MOCK_LLM, components
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from models.OpenAIModel import OpenAIModel
from openai import OpenAIError, RateLimitError
from utils.types import AgentResponse, Status


class SpecAgent(BaseAgent):
    """
    Generates a detailed JSON specification for a planned circuit given
    a high-level overview of the user's business needs.
    """

    def _mock(self, prompt: str) -> str:
        return str(
            {
                "goal": f"Interpret user request: {prompt}",
                "inputs": ["5V supply", "1x pushbutton (optional)"],
                "outputs": ["1x LED blinking at ~1 Hz"],
                "constraints": {"max_current_mA": 10, "breadboard_layout": True},
                "notes": ["This is MOCK mode output", "Replace with real LLM later"],
            }
        )

    async def run(self, model: str, prompt: str) -> AgentResponse:
        if USE_MOCK_LLM:
            mock_response = AgentResponse(response=self._mock(prompt), status=Status.SUCCESS)
            return mock_response

        # sets up the LLM pipeline
        # we create a prompt template with the prompt and whatever input variables
        # we'd like to add in (e.g. context). Then we pass the result to our LLM, and then
        # parse the generated text in JSON format
        llm = OpenAIModel(model).getModel()
        prompt_template = PromptTemplate(
            template=SPEC_GENERATION_PROMPT, input_variables=["user_prompt", "components"]
        )
        parser = JsonOutputParser()
        chain = prompt_template | llm | parser

        try:
            generated_spec = await asyncio.to_thread(
                chain.invoke,
                {"user_prompt": prompt, "components": components},
            )
        except RateLimitError as e:  # ask matt to buy more OpenAI credits
            err_message = f"OpenAI quota exceeded with message: {e}"
            print("RateLimitError:", e)
            return AgentResponse(response="", status=Status.ERROR, err_message=err_message)
        except (
            OpenAIError
        ) as e:  # something's usually wrong on OpenAI's side or the model is broken
            err_message = f"Encountered OpenAI error with message {e}"
            print("OpenAI API Error:", e)
            return AgentResponse(response="", status=Status.ERROR, err_message=err_message)
        # for all other exceptions, we generally want the program to end "loudly" so that we can fix the bug

        return AgentResponse(response=generated_spec, status=Status.SUCCESS)
