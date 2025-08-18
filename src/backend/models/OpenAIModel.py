from typing import AsyncGenerator, Dict, List

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
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

    def setParams(self, modelName: str | None = None, temperature: float | None = None):
        """
        Update model parameters and rebuild the underlying ChatOpenAI instance.
        """
        if modelName is not None:
            self.model_name = modelName
        if temperature is not None:
            self.temperature = temperature
        self.llm = ChatOpenAI(model=self.model_name, temperature=self.temperature)

    @staticmethod
    def toLangChainMessages(messages: List[Dict]) -> List:
        """
        Convert simple role/content dicts into LangChain message objects.
        """
        role_map = {
            "system": SystemMessage,
            "user": HumanMessage,
            "assistant": AIMessage,
        }
        return [role_map[m["role"]](content=m["content"]) for m in messages]

    async def streamChat(self, messages: List[Dict]) -> AsyncGenerator[str, None]:
        """
        Stream assistant text deltas for the given chat messages.
        Yields incremental text chunks as they arrive.
        """
        lc_messages = self.toLangChainMessages(messages)
        async for chunk in self.llm.astream(lc_messages):
            # chunk is an AIMessageChunk; chunk.content is the new delta content
            if getattr(chunk, "content", None):
                yield chunk.content
