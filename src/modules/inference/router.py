import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from src.modules.inference.models import ALLOWED_MODELS, DEFAULT_MODEL, is_model_allowed
from src.modules.inference.schemas import ChatRequest, ModelResponse
from src.modules.inference.service import inference_service

router = APIRouter()


@router.get("/models")
async def list_models() -> dict:
    models = [
        ModelResponse(id=m.id, name=m.name, provider=m.provider)
        for m in ALLOWED_MODELS.values()
    ]
    return {"models": models, "default": DEFAULT_MODEL}


@router.post("/chat")
async def chat(request: ChatRequest) -> StreamingResponse:
    if not is_model_allowed(request.model):
        raise HTTPException(
            status_code=422,
            detail=f"Model '{request.model}' is not supported. Use GET /api/inference/models for available models.",
        )

    messages = [msg.model_dump() for msg in request.messages]

    async def event_stream():
        async for token in inference_service.stream_chat(
            messages=messages,
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        ):
            yield f"data: {json.dumps({'token': token})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
