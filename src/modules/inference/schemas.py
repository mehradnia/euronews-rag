import uuid

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    conversation_id: uuid.UUID
    content: str
    model_id: str
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=16384, ge=1, le=131072)


class ModelResponse(BaseModel):
    id: str
    name: str
    provider: str
