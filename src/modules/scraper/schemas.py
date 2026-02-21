from datetime import datetime

from pydantic import BaseModel


class ArticleListItem(BaseModel):
    """Metadata extracted from a listing-page card."""

    title: str
    url: str
    summary: str
    publication_date: str  # raw string; parsed when the full article is built


class ScrapedArticle(BaseModel):
    """Complete article after scraping the individual article page."""

    title: str
    url: str
    summary: str
    category: str | None = None
    publication_date: datetime | None = None
    content: str


class ScrapeResult(BaseModel):
    """Aggregated result of a full scrape run."""

    articles: list[ScrapedArticle]
    total: int
    failed: int
