import asyncio
import time
import uuid
from typing import Any, AsyncGenerator, Dict, List

from config import USE_MOCK_LLM
from models.OpenAIModel import OpenAIModel
from utils.types import AgentResponse, Status

from agents.BaseAgent import BaseAgent


class ChatAgent(BaseAgent):
    """
    Streaming-first chat agent that yields SSE-friendly events:
      - message_start
      - chunk
      - message_end
    """

    def _mock(self, prompt: str) -> AgentResponse:
        return AgentResponse(
            response="This is a mock streaming reply. Replace with the real LLM when ready.",
            status=Status.SUCCESS,
        )

    async def run(self: str, prompt: str) -> AgentResponse:
        pass

    # TODO: consolidate the base agent class to support passing model info and better handle config
    async def stream(
        self,
        messages: List[Dict[str, str]],
        modelName: str,
        temperature: float = 0.7,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        msg_id = str(uuid.uuid4())
        created = time.time()

        yield {"type": "message_start", "id": msg_id, "model": modelName, "created": created}

        if USE_MOCK_LLM:
            mocked_text = self._mock("").response
            for piece in mocked_text.split(" "):
                await asyncio.sleep(0.02)
                yield {"type": "chunk", "id": msg_id, "delta": piece + " "}
            yield {"type": "message_end", "id": msg_id, "content": mocked_text, "usage": {}}
            return

        model = OpenAIModel(model_name=modelName, temperature=temperature)
        content_parts: List[str] = []

        try:
            async for delta in model.streamChat(messages):
                if delta:
                    content_parts.append(delta)
                    yield {"type": "chunk", "id": msg_id, "delta": delta}
        except Exception as e:
            yield {"type": "error", "id": msg_id, "message": str(e)}
            return

        full = "".join(content_parts)
        yield {"type": "message_end", "id": msg_id, "content": full}
