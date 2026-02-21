from datetime import datetime

from pydantic import BaseModel

from src.modules.scraper.schemas import ScrapedArticle


class ProcessedChunk(BaseModel):
    content: str
    title: str
    url: str
    category: str | None = None
    publication_date: datetime | None = None
    chunk_index: int


class PreprocessResult(BaseModel):
    articles: list[ScrapedArticle]
    chunks: list[ProcessedChunk]
