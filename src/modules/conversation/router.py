import uuid

from fastapi import APIRouter, HTTPException

from src.modules.conversation.schemas import (
    ConversationDetailResponse,
    ConversationResponse,
    CreateConversation,
)
from src.modules.persistence.service import persistence_service

router = APIRouter()


@router.post("", response_model=ConversationResponse, status_code=201)
async def create_conversation(body: CreateConversation):
    return await persistence_service.create_conversation(title=body.title)


@router.get("", response_model=list[ConversationResponse])
async def list_conversations():
    return await persistence_service.list_conversations()


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(conversation_id: uuid.UUID):
    conversation = await persistence_service.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(conversation_id: uuid.UUID):
    deleted = await persistence_service.delete_conversation(conversation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")
