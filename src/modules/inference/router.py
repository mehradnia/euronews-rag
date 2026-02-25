import json
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from src.modules.embedder.service import embedder_service
from src.modules.inference.models import ALLOWED_MODELS, DEFAULT_MODEL, is_model_allowed
from src.modules.inference.schemas import ChatRequest, ModelResponse
from src.modules.inference.service import inference_service
from src.modules.persistence.service import persistence_service

logger = logging.getLogger(__name__)

router = APIRouter()

SYSTEM_PROMPT_TEMPLATE = """\
You are a helpful assistant that answers questions based on the provided context from news articles.
Use the following context to answer the user's question. If the context doesn't contain relevant information, say so.

Context:
{context}"""


def _build_context(sources) -> str:
    # Deduplicate by document URL — use full document content, not just the chunk
    seen: set[str] = set()
    blocks: list[str] = []
    for s in sources:
        if s.document_url in seen:
            continue
        seen.add(s.document_url)
        meta_parts = [s.document_title]
        if s.document_category:
            meta_parts.append(s.document_category)
        if s.document_publication_date:
            meta_parts.append(s.document_publication_date.strftime("%Y-%m-%d"))
        header = " | ".join(meta_parts)
        blocks.append(f"---\n{header}\nURL: {s.document_url}\n{s.document_content}\n---")
    return "\n\n".join(blocks)


@router.get("/models")
async def list_models() -> dict:
    models = [
        ModelResponse(id=m.id, name=m.name, provider=m.provider)
        for m in ALLOWED_MODELS.values()
    ]
    return {"models": models, "default": DEFAULT_MODEL}


@router.post("/chat")
async def chat(request: ChatRequest) -> StreamingResponse:
    if not is_model_allowed(request.model_id):
        raise HTTPException(
            status_code=422,
            detail=f"Model '{request.model_id}' is not supported.",
        )

    conversation = await persistence_service.get_conversation(request.conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Cap max_tokens to the model's limit
    model_info = ALLOWED_MODELS[request.model_id]
    max_tokens = min(request.max_tokens, model_info.max_tokens)

    # RAG retrieval
    query_embedding = await embedder_service.embed_query(request.content)
    sources = await persistence_service.search_similar(query_embedding, limit=request.top_k)
    logger.info("Retrieved %d chunks for query", len(sources))

    # Build messages with context + conversation history
    context = _build_context(sources)
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(context=context)
    history = [
        {"role": msg.role, "content": msg.content}
        for msg in (conversation.messages or [])
        if msg.role in ("user", "assistant")
    ][-10:]
    messages = [
        {"role": "system", "content": system_prompt},
        *history,
        {"role": "user", "content": request.content},
    ]

    # Persist user message
    await persistence_service.add_message(
        request.conversation_id, role="user", content=request.content
    )

    # Group sources by document (deduplicate, keep all chunks per doc)
    doc_map: dict[str, dict] = {}
    for s in sources:
        url = s.document_url
        if url not in doc_map:
            doc_map[url] = {
                "document_title": s.document_title,
                "document_url": url,
                "document_content": s.document_content,
                "document_category": s.document_category,
                "document_publication_date": (
                    s.document_publication_date.isoformat()
                    if s.document_publication_date
                    else None
                ),
                "chunks": [],
            }
        doc_map[url]["chunks"].append({
            "content": s.chunk_content,
            "chunk_index": s.chunk_index,
            "similarity": round(s.similarity, 4),
        })
    sources_payload = list(doc_map.values())

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
                await persistence_service.add_message(
                    request.conversation_id, role="assistant",
                    content=assistant_content, model_id=request.model_id,
                    sources=sources_payload,
                )
        yield f"data: {json.dumps({'sources': sources_payload})}\n\n"
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
