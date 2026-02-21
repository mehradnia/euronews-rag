import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.database import get_db
from src.modules.conversation import service as conversation_service
from src.modules.inference.models import ALLOWED_MODELS, DEFAULT_MODEL, is_model_allowed
from src.modules.inference.schemas import ChatRequest, ModelResponse
from src.modules.inference.service import inference_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/models")
async def list_models() -> dict:
    models = [
        ModelResponse(id=m.id, name=m.name, provider=m.provider)
        for m in ALLOWED_MODELS.values()
    ]
    return {"models": models, "default": DEFAULT_MODEL}


@router.post("/chat")
async def chat(
    request: ChatRequest, db: AsyncSession = Depends(get_db)
) -> StreamingResponse:
    if not is_model_allowed(request.model_id):
        raise HTTPException(
            status_code=422,
            detail=f"Model '{request.model_id}' is not supported.",
        )

    conversation = await conversation_service.get_conversation(db, request.conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Cap max_tokens to the model's limit
    model_info = ALLOWED_MODELS[request.model_id]
    max_tokens = min(request.max_tokens, model_info.max_tokens)

    # No memory — only send the current user message
    messages = [{"role": "user", "content": request.content}]

    # Persist user message
    await conversation_service.add_message(
        db, request.conversation_id, role="user", content=request.content
    )

    async def event_stream():
        full_response: list[str] = []
        try:
            async for token in inference_service.stream_chat(
                messages=messages,
                model=request.model_id,
                temperature=request.temperature,
                max_tokens=max_tokens,
            ):
                full_response.append(token)
                yield f"data: {json.dumps({'token': token})}\n\n"
        except Exception as exc:
            logger.exception("Inference error for model %s", request.model_id)
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"
        else:
            assistant_content = "".join(full_response)
            if assistant_content:
                await conversation_service.add_message(
                    db, request.conversation_id, role="assistant",
                    content=assistant_content, model_id=request.model_id,
                )
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Content-Encoding": "none",
        },
    )
