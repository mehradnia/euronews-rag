import html
import logging
import re
import unicodedata

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langdetect import detect
from langdetect.lang_detect_exception import LangDetectException

from src.modules.preprocessor.composer import PreprocessorComposer
from src.modules.preprocessor.schemas import PreprocessResult, ProcessedChunk
from src.modules.scraper.schemas import ScrapedArticle

logger = logging.getLogger(__name__)

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150
MIN_CONTENT_LENGTH = 50


class PreprocessorService:
    def __init__(self) -> None:
        self._composer = PreprocessorComposer()
        self._composer.add_step("clean", self._clean)
        self._composer.add_step("normalize", self._normalize)
        self._composer.add_step("filter_language", self._filter_language)
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
        )

    async def _clean(self, articles: list[ScrapedArticle]) -> list[ScrapedArticle]:
        cleaned: list[ScrapedArticle] = []
        for article in articles:
            content = html.unescape(article.content)
            content = re.sub(r"\s+", " ", content).strip()
            title = html.unescape(article.title).strip()
            cleaned.append(article.model_copy(update={"content": content, "title": title}))
        return cleaned

    async def _normalize(self, articles: list[ScrapedArticle]) -> list[ScrapedArticle]:
        normalized: list[ScrapedArticle] = []
        for article in articles:
            content = unicodedata.normalize("NFKD", article.content)
            content = content.replace("\u2018", "'").replace("\u2019", "'")
            content = content.replace("\u201c", '"').replace("\u201d", '"')
            content = content.replace("\u2013", "-").replace("\u2014", "-")
            title = unicodedata.normalize("NFKD", article.title)
            normalized.append(article.model_copy(update={"content": content, "title": title}))
        return normalized

    async def _filter_language(self, articles: list[ScrapedArticle]) -> list[ScrapedArticle]:
        filtered: list[ScrapedArticle] = []
        for article in articles:
            if len(article.content) < MIN_CONTENT_LENGTH:
                logger.info("Skipped (too short): %s", article.title)
                continue
            try:
                lang = detect(article.content)
            except LangDetectException:
                logger.warning("Language detection failed: %s", article.title)
                continue
            if lang != "en":
                logger.info("Skipped (lang=%s): %s", lang, article.title)
                continue
            filtered.append(article)
        return filtered

    def _chunk(self, articles: list[ScrapedArticle]) -> list[ProcessedChunk]:
        chunks: list[ProcessedChunk] = []
        for article in articles:
            prefix = f"{article.title}: "
            splits = self._splitter.split_text(article.content)
            for i, text in enumerate(splits):
                chunks.append(
                    ProcessedChunk(
                        content=prefix + text,
                        title=article.title,
                        url=article.url,
                        category=article.category,
                        publication_date=article.publication_date,
                        chunk_index=i,
                    )
                )
        return chunks

    async def preprocess(self, articles: list[ScrapedArticle]) -> PreprocessResult:
        cleaned = await self._composer.run(articles)
        chunks = self._chunk(cleaned)
        logger.info("Preprocessing complete: %d chunks from %d articles", len(chunks), len(cleaned))
        return PreprocessResult(articles=cleaned, chunks=chunks)


preprocessor_service = PreprocessorService()
