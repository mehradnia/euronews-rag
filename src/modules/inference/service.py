from collections.abc import AsyncIterator

from huggingface_hub import InferenceClient

from src.config.settings import settings


class InferenceService:
    def __init__(self) -> None:
        self._client = InferenceClient(
            token=settings.hf_api_token,
        )

    async def stream_chat(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AsyncIterator[str]:
        stream = self._client.chat_completion(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )

        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


inference_service = InferenceService()
