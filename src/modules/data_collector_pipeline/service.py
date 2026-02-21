import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.modules.data_collector_pipeline.composer import PipelineComposer
from src.modules.embedder.service import embedder_service
from src.modules.persistence.service import persistence_service
from src.modules.preprocessor.schemas import PreprocessResult
from src.modules.scraper.schemas import ScrapedArticle
from src.modules.scraper.service import scraper_service
from src.modules.preprocessor.service import preprocessor_service

logger = logging.getLogger(__name__)

SCRAPE_DATE_FROM = datetime(2026, 1, 21, 18, 45, 59)


class DataCollectorPipelineService:
    def __init__(self) -> None:
        self._composer = PipelineComposer()
        self._composer.add_step("scrape", self._scrape)
        self._composer.add_step("preprocess", self._preprocess)
        self._composer.add_step("embed", self._embed)
        self._scheduler = AsyncIOScheduler()
        self._scraped_articles: list[ScrapedArticle] = []
        self._preprocess_result: PreprocessResult | None = None

    async def _scrape(self) -> None:
        result = await scraper_service.scrape(SCRAPE_DATE_FROM)
        self._scraped_articles = result.articles
        logger.info("Scrape step collected %d articles", result.total)

    async def _preprocess(self) -> None:
        self._preprocess_result = await preprocessor_service.preprocess(self._scraped_articles)
        logger.info(
            "Preprocess step produced %d chunks from %d articles",
            len(self._preprocess_result.chunks),
            len(self._preprocess_result.articles),
        )

    async def _embed(self) -> None:
        result = self._preprocess_result
        embeddings = await embedder_service.embed(result.chunks)
        await persistence_service.batch_store(result.articles, result.chunks, embeddings)
        logger.info("Embed step completed")

    async def start(self) -> None:
        await self._composer.run()
        self._scheduler.add_job(
            self._composer.run,
            CronTrigger(hour=3, minute=0),
            id="data_collector_pipeline",
            replace_existing=True,
        )
        self._scheduler.start()
        logger.info("Scheduler started — pipeline runs daily at 03:00")

    async def stop(self) -> None:
        self._scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")


data_collector_pipeline_service = DataCollectorPipelineService()
