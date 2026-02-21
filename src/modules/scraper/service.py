import asyncio
import logging
import re
from datetime import datetime
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup

from src.modules.scraper.schemas import (
    ArticleListItem,
    ScrapedArticle,
    ScrapeResult,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://commission.europa.eu"
NEWS_PATH = "/news-and-media/news_en"
ITEMS_PER_PAGE = 10
MAX_CONCURRENCY = 5
REQUEST_DELAY = 1.0
REQUEST_TIMEOUT = 30.0
MAX_RETRIES = 3

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}


class ScraperService:
    """Scrapes European Commission news articles."""

    # ── HTTP layer ──────────────────────────────────────────────

    async def _fetch(self, client: httpx.AsyncClient, url: str) -> str:
        last_exc: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                await asyncio.sleep(REQUEST_DELAY)
                response = await client.get(
                    url,
                    headers=_HEADERS,
                    timeout=REQUEST_TIMEOUT,
                    follow_redirects=True,
                )
                response.raise_for_status()
                return response.text
            except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                last_exc = exc
                wait = 2 ** attempt
                logger.warning(
                    "Attempt %d/%d failed for %s: %s — retrying in %ds",
                    attempt, MAX_RETRIES, url, exc, wait,
                )
                await asyncio.sleep(wait)
        raise last_exc  # type: ignore[misc]

    # ── URL building ────────────────────────────────────────────

    @staticmethod
    def _build_listing_url(date_from: datetime, page: int) -> str:
        date_str = date_from.strftime("%Y-%m-%dT%H:%M:%S+01:00")
        filter_value = f"oe_news_publication_date:gt|{date_str}"
        return f"{BASE_URL}{NEWS_PATH}?f[0]={quote(filter_value)}&page={page}"

    # ── Parsing layer ───────────────────────────────────────────

    @staticmethod
    def _parse_listing_page(html: str) -> list[ArticleListItem]:
        soup = BeautifulSoup(html, "lxml")
        articles: list[ArticleListItem] = []

        for block in soup.select(".ecl-content-block"):
            title_el = block.select_one(".ecl-content-block__title")
            if not title_el:
                continue
            link_el = title_el.select_one("a")
            if not link_el:
                continue

            # Skip non-article blocks (no metadata = navigation element)
            meta_items = block.select(".ecl-content-block__primary-meta-item")
            if len(meta_items) < 2:
                continue

            href = link_el.get("href", "")
            if href and not href.startswith("http"):
                href = f"{BASE_URL}{href}"

            category = meta_items[0].get_text(strip=True)
            date_raw = meta_items[1].get_text(strip=True)

            articles.append(
                ArticleListItem(
                    title=link_el.get_text(strip=True),
                    url=str(href),
                    summary=category,
                    publication_date=date_raw,
                )
            )
        return articles

    @staticmethod
    def _detect_total_pages(html: str) -> int:
        soup = BeautifulSoup(html, "lxml")
        max_page = 0
        for link in soup.select(".ecl-pagination__item a"):
            href = link.get("href", "")
            match = re.search(r"page=(\d+)", href)
            if match:
                max_page = max(max_page, int(match.group(1)))
        if max_page > 0:
            return max_page + 1  # zero-based → count
        # Fallback: count items on first page and assume single page
        items = soup.select(".ecl-content-block")
        return 1 if items else 0

    @staticmethod
    def _parse_article_page(html: str, list_item: ArticleListItem) -> ScrapedArticle:
        soup = BeautifulSoup(html, "lxml")

        # Title: prefer h1, fall back to og:title, then listing title
        h1 = soup.select_one("h1")
        title = h1.get_text(strip=True) if h1 else ""
        if not title or title.lower() in ("navigation", "press corner"):
            og_title = soup.find("meta", property="og:title")
            title = og_title["content"] if og_title else list_item.title

        # Category from breadcrumbs
        breadcrumbs = soup.select(
            ".ecl-breadcrumb__link, .ecl-breadcrumb__current-page"
        )
        category = breadcrumbs[-2].get_text(strip=True) if len(breadcrumbs) >= 2 else None

        # Date
        publication_date: datetime | None = None
        if list_item.publication_date:
            try:
                publication_date = datetime.strptime(
                    list_item.publication_date, "%d %B %Y"
                )
            except ValueError:
                logger.warning(
                    "Could not parse date '%s' for %s",
                    list_item.publication_date, list_item.url,
                )

        # Content — gather paragraphs from the main content area
        content_area = (
            soup.select_one("article")
            or soup.select_one(".ecl-editor")
            or soup.select_one("main")
        )
        if content_area:
            paragraphs = content_area.find_all("p")
            content = "\n\n".join(
                p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)
            )
        else:
            content = ""

        # Fallback for SPA pages (presscorner): use meta description
        if not content:
            meta_desc = soup.find("meta", property="og:description") or soup.find(
                "meta", attrs={"name": "description"}
            )
            if meta_desc and meta_desc.get("content"):
                content = meta_desc["content"].strip()

        return ScrapedArticle(
            title=title,
            url=list_item.url,
            summary=list_item.summary,
            category=category,
            publication_date=publication_date,
            content=content,
        )

    # ── Orchestration ───────────────────────────────────────────

    async def scrape(self, date_from: datetime) -> ScrapeResult:
        all_list_items: list[ArticleListItem] = []
        articles: list[ScrapedArticle] = []
        failed = 0
        semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

        async with httpx.AsyncClient() as client:

            # ── Phase 1: listing pages ──
            logger.info("Phase 1: scraping listing pages (date_from=%s)", date_from.isoformat())

            first_url = self._build_listing_url(date_from, page=0)
            first_html = await self._fetch(client, first_url)
            total_pages = self._detect_total_pages(first_html)
            logger.info("Detected %d listing pages", total_pages)

            all_list_items.extend(self._parse_listing_page(first_html))

            for page in range(1, total_pages):
                url = self._build_listing_url(date_from, page)
                try:
                    html = await self._fetch(client, url)
                    all_list_items.extend(self._parse_listing_page(html))
                except Exception:
                    logger.exception("Failed listing page %d", page)

            # Deduplicate by URL (highlighted cards appear twice)
            seen_urls: set[str] = set()
            unique_items: list[ArticleListItem] = []
            for item in all_list_items:
                if item.url not in seen_urls:
                    seen_urls.add(item.url)
                    unique_items.append(item)
            logger.info(
                "Phase 1 complete: %d raw, %d after dedup",
                len(all_list_items), len(unique_items),
            )
            all_list_items = unique_items

            # ── Phase 2: individual articles ──
            logger.info("Phase 2: scraping %d individual articles", len(all_list_items))

            async def fetch_article(item: ArticleListItem) -> ScrapedArticle | None:
                async with semaphore:
                    try:
                        html = await self._fetch(client, item.url)
                        return self._parse_article_page(html, item)
                    except Exception:
                        logger.exception("Failed article %s", item.url)
                        return None

            article_tasks = [fetch_article(item) for item in all_list_items]
            article_results = await asyncio.gather(*article_tasks)

            for result in article_results:
                if result is not None:
                    articles.append(result)
                    logger.info(
                        "Scraped: [%s] %s (%d chars)",
                        result.publication_date,
                        result.title,
                        len(result.content),
                    )
                else:
                    failed += 1

        logger.info(
            "Scraping complete: %d articles scraped, %d failed",
            len(articles), failed,
        )

        return ScrapeResult(articles=articles, total=len(articles), failed=failed)


scraper_service = ScraperService()
