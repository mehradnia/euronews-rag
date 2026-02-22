import logging
import uuid

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import selectinload

from src.config.database import async_session
from src.modules.persistence.contracts import (
    ConversationContract,
    DocumentContract,
    VectorSearchContract,
)
from src.modules.persistence.models import Chunk, Conversation, Document, Message
from src.modules.persistence.schemas import SearchResult
from src.modules.preprocessor.schemas import ProcessedChunk
from src.modules.scraper.schemas import ScrapedArticle

logger = logging.getLogger(__name__)


class PersistenceService(ConversationContract, DocumentContract, VectorSearchContract):

    # ── Conversation ─────────────────────────────────────────────

    async def create_conversation(self, title: str) -> Conversation:
        async with async_session() as session:
            conversation = Conversation(title=title)
            session.add(conversation)
            await session.commit()
            await session.refresh(conversation)
            return conversation

    async def list_conversations(self) -> list[Conversation]:
        async with async_session() as session:
            result = await session.execute(
                select(Conversation).order_by(Conversation.updated_at.desc())
            )
            return list(result.scalars().all())

    async def get_conversation(self, conversation_id: uuid.UUID) -> Conversation | None:
        async with async_session() as session:
            result = await session.execute(
                select(Conversation)
                .where(Conversation.id == conversation_id)
                .options(selectinload(Conversation.messages))
            )
            return result.scalar_one_or_none()

    async def delete_conversation(self, conversation_id: uuid.UUID) -> bool:
        async with async_session() as session:
            conversation = await session.get(Conversation, conversation_id)
            if not conversation:
                return False
            await session.delete(conversation)
            await session.commit()
            return True

    async def add_message(
        self,
        conversation_id: uuid.UUID,
        role: str,
        content: str,
        model_id: str | None = None,
        sources: list | None = None,
    ) -> Message | None:
        async with async_session() as session:
            conversation = await session.get(Conversation, conversation_id)
            if not conversation:
                return None
            message = Message(
                conversation_id=conversation_id,
                role=role,
                content=content,
                model_id=model_id,
                sources=sources,
            )
            session.add(message)
            await session.commit()
            await session.refresh(message)
            return message

    # ── Documents ────────────────────────────────────────────────

    async def batch_store(
        self,
        articles: list[ScrapedArticle],
        chunks: list[ProcessedChunk],
        embeddings: list[list[float]],
    ) -> int:
        async with async_session() as session:
            # 1. Upsert documents by URL
            doc_map: dict[str, uuid.UUID] = {}
            for article in articles:
                stmt = (
                    insert(Document)
                    .values(
                        url=article.url,
                        title=article.title,
                        category=article.category,
                        publication_date=article.publication_date,
                        content=article.content,
                    )
                    .on_conflict_do_update(
                        index_elements=["url"],
                        set_={
                            "title": article.title,
                            "category": article.category,
                            "publication_date": article.publication_date,
                            "content": article.content,
                        },
                    )
                    .returning(Document.id)
                )
                result = await session.execute(stmt)
                doc_id = result.scalar_one()
                doc_map[article.url] = doc_id

            # 2. Delete old chunks for these documents
            doc_ids = list(doc_map.values())
            await session.execute(
                delete(Chunk).where(Chunk.document_id.in_(doc_ids))
            )

            # 3. Insert new chunks with embeddings
            chunk_rows = []
            for chunk, embedding in zip(chunks, embeddings):
                doc_id = doc_map.get(chunk.url)
                if doc_id is None:
                    continue
                chunk_rows.append(
                    Chunk(
                        document_id=doc_id,
                        chunk_index=chunk.chunk_index,
                        content=chunk.content,
                        embedding=embedding,
                    )
                )

            session.add_all(chunk_rows)
            await session.commit()

        logger.info(
            "Stored %d documents, %d chunks", len(doc_map), len(chunk_rows)
        )
        return len(doc_map)

    # ── Vector Search ────────────────────────────────────────────

    async def search_similar(
        self,
        query_embedding: list[float],
        limit: int = 5,
    ) -> list[SearchResult]:
        async with async_session() as session:
            distance = Chunk.embedding.cosine_distance(query_embedding)
            result = await session.execute(
                select(Chunk, Document, distance.label("distance"))
                .join(Document, Chunk.document_id == Document.id)
                .order_by(distance)
                .limit(limit)
            )

            results = []
            for chunk, document, dist in result.all():
                results.append(
                    SearchResult(
                        chunk_content=chunk.content,
                        chunk_index=chunk.chunk_index,
                        similarity=1 - dist,
                        document_title=document.title,
                        document_url=document.url,
                        document_content=document.content,
                        document_category=document.category,
                        document_publication_date=document.publication_date,
                    )
                )
            return results


persistence_service = PersistenceService()
