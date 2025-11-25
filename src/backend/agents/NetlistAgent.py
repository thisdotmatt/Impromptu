from agents.BaseAgent import BaseAgent
from config import NETLIST_GENERATION_PROMPT, MOCK_NETLIST, USE_MOCK_LLM, components
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from models.OpenAIModel import OpenAIModel
from openai import OpenAIError, RateLimitError
from utils.types import AgentResponse, Status
import asyncio

class NetlistAgent(BaseAgent):
    """
    Takes in a pre-defined electrical specification and converts this into a netlist.
    The generated netlist is NOT verified - this agent is strictly for generation.
    We use open source tools and similar to verify the functionality of the netlist
    and retry if necessary. See src/backend/workflows/NetlistWorkflow.py
    """

    def _mock(self, prompt: str) -> str:
        return MOCK_NETLIST
        # return (
        #     "* LED with resistor and 5V source\n"
        #     "V1 N001 0 DC 5\n"
        #     "R1 N001 N002 330\n"
        #     "D1 N002 0 DLED\n"
        #     ".model DLED D (IS=1e-14 N=1.7 BV=100 IBV=0.1 CJO=10p RS=10 TT=1u)\n"
        #     ".end"
        # )

    async def run(self, model: str, prompt: str) -> AgentResponse:
            if USE_MOCK_LLM:
                mock_response = AgentResponse(response=self._mock(prompt), status=Status.SUCCESS)
                return mock_response

            llm = OpenAIModel(model).getModel()
            prompt_template = PromptTemplate(
                template=NETLIST_GENERATION_PROMPT, input_variables=["components", "specification"]
            )
            parser = StrOutputParser()
            chain = prompt_template | llm | parser

            try:
                netlist_text = await asyncio.to_thread(
                    chain.invoke,
                    {"components": components, "specification": prompt},
                )
            except RateLimitError as e:
                err_message = f"OpenAI quota exceeded with message: {e}"
                print("RateLimitError:", e)
                return AgentResponse(response="", status=Status.ERROR, err_message=err_message)
            except OpenAIError as e:
                err_message = f"Encountered OpenAI error with message {e}"
                print("OpenAI API Error:", e)
                return AgentResponse(response="", status=Status.ERROR, err_message=err_message)

            return AgentResponse(response=netlist_text, status=Status.SUCCESS)