import logging
from collections.abc import Awaitable, Callable

from src.modules.scraper.schemas import ScrapedArticle

logger = logging.getLogger(__name__)

PreprocessStep = Callable[[list[ScrapedArticle]], Awaitable[list[ScrapedArticle]]]


class PreprocessorComposer:
    """Manages an ordered sequence of async preprocessing steps."""

    def __init__(self) -> None:
        self._steps: list[tuple[str, PreprocessStep]] = []

    def add_step(self, name: str, step: PreprocessStep) -> None:
        self._steps.append((name, step))

    async def run(self, articles: list[ScrapedArticle]) -> list[ScrapedArticle]:
        logger.info("Preprocessor started (%d steps, %d articles)", len(self._steps), len(articles))
        for name, step in self._steps:
            articles = await step(articles)
            logger.info("Step '%s': %d articles remaining", name, len(articles))
        logger.info("Preprocessor finished: %d articles", len(articles))
        return articles
