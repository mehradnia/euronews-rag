from collections.abc import AsyncIterator

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint

from src.config.settings import settings

ROLE_TO_MESSAGE = {
    "user": HumanMessage,
    "assistant": AIMessage,
    "system": SystemMessage,
}


class InferenceService:
    def __init__(self) -> None:
        self._token = settings.hf_api_token

    def _build_chat_model(
        self, model: str, temperature: float, max_tokens: int
    ) -> ChatHuggingFace:
        llm = HuggingFaceEndpoint(
            repo_id=model,
            huggingfacehub_api_token=self._token,
            provider="auto",
            task="text-generation",
            temperature=temperature,
            max_new_tokens=max_tokens,
        )
        return ChatHuggingFace(llm=llm)

    async def stream_chat(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 16384,
    ) -> AsyncIterator[str]:
        chat_model = self._build_chat_model(model, temperature, max_tokens)
        lc_messages = [
            ROLE_TO_MESSAGE[msg["role"]](content=msg["content"])
            for msg in messages
        ]
        async for chunk in chat_model.astream(lc_messages):
            if chunk.content:
                yield chunk.content


inference_service = InferenceService()
