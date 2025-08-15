from langchain_openai import ChatOpenAI
from models.BaseModel import BaseModel

class OpenAIModel(BaseModel):
    """
    Implementation of BaseModel for OpenAI LLMs using langchain_openai.ChatOpenAI.
    """
    def __init__(self, model_name="gpt-4o-mini", temperature=0.7):
        super().__init__(model_name, temperature)
        self.llm = ChatOpenAI(model=self.model_name, temperature=self.temperature)

    def getModel(self):
        return self.llm
