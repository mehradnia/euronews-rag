from datetime import datetime

from pydantic import BaseModel


class SearchResult(BaseModel):
    chunk_content: str
    chunk_index: int
    similarity: float
    document_title: str
    document_url: str
    document_content: str
    document_category: str | None = None
    document_publication_date: datetime | None = None
