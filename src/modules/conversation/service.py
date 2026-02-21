import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.modules.conversation.models import Conversation, Message


async def create_conversation(
    db: AsyncSession, title: str
) -> Conversation:
    conversation = Conversation(title=title)
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    return conversation


async def list_conversations(db: AsyncSession) -> list[Conversation]:
    result = await db.execute(
        select(Conversation).order_by(Conversation.updated_at.desc())
    )
    return list(result.scalars().all())


async def get_conversation(
    db: AsyncSession, conversation_id: uuid.UUID
) -> Conversation | None:
    result = await db.execute(
        select(Conversation)
        .where(Conversation.id == conversation_id)
        .options(selectinload(Conversation.messages))
    )
    return result.scalar_one_or_none()


async def delete_conversation(
    db: AsyncSession, conversation_id: uuid.UUID
) -> bool:
    conversation = await db.get(Conversation, conversation_id)
    if not conversation:
        return False
    await db.delete(conversation)
    await db.commit()
    return True


async def add_message(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    role: str,
    content: str,
    model_id: str | None = None,
) -> Message | None:
    conversation = await db.get(Conversation, conversation_id)
    if not conversation:
        return None
    message = Message(
        conversation_id=conversation_id, role=role, content=content, model_id=model_id
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)
    return message
