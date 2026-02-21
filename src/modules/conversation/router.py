import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.database import get_db
from src.modules.conversation import service
from src.modules.conversation.schemas import (
    ConversationDetailResponse,
    ConversationResponse,
    CreateConversation,
)

router = APIRouter()


@router.post("", response_model=ConversationResponse, status_code=201)
async def create_conversation(
    body: CreateConversation, db: AsyncSession = Depends(get_db)
):
    return await service.create_conversation(db, title=body.title)


@router.get("", response_model=list[ConversationResponse])
async def list_conversations(db: AsyncSession = Depends(get_db)):
    return await service.list_conversations(db)


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conversation_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    conversation = await service.get_conversation(db, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    deleted = await service.delete_conversation(db, conversation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")
