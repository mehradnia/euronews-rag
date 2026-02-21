import uuid
from abc import ABC, abstractmethod
from datetime import datetime

from src.modules.persistence.schemas import SearchResult
from src.modules.preprocessor.schemas import ProcessedChunk
from src.modules.scraper.schemas import ScrapedArticle


class ConversationContract(ABC):
    @abstractmethod
    async def create_conversation(self, title: str) -> object: ...

    @abstractmethod
    async def list_conversations(self) -> list: ...

    @abstractmethod
    async def get_conversation(self, conversation_id: uuid.UUID) -> object | None: ...

    @abstractmethod
    async def delete_conversation(self, conversation_id: uuid.UUID) -> bool: ...

    @abstractmethod
    async def add_message(
        self,
        conversation_id: uuid.UUID,
        role: str,
        content: str,
        model_id: str | None = None,
    ) -> object | None: ...


class DocumentContract(ABC):
    @abstractmethod
    async def batch_store(
        self,
        articles: list[ScrapedArticle],
        chunks: list[ProcessedChunk],
        embeddings: list[list[float]],
    ) -> int: ...


class VectorSearchContract(ABC):
    @abstractmethod
    async def search_similar(
        self,
        query_embedding: list[float],
        limit: int = 5,
    ) -> list[SearchResult]: ...
