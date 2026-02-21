"""
WebCrawler Connector Module

A module for crawling web pages and extracting content using Firecrawl,
plain HTTP+Trafilatura, or Playwright.  Provides a unified interface for
web scraping.

Fallback order:
  1. Firecrawl  (if API key is configured)
  2. HTTP + Trafilatura  (lightweight, works on any event loop)
  3. Playwright / Chromium  (runs in a thread to avoid event-loop limitations)
"""

import asyncio
import logging
from typing import Any

import httpx
import trafilatura
import validators
from fake_useragent import UserAgent
from firecrawl import AsyncFirecrawlApp
from playwright.sync_api import sync_playwright

from app.utils.proxy_config import get_playwright_proxy, get_residential_proxy_url

logger = logging.getLogger(__name__)


class WebCrawlerConnector:
    """Class for crawling web pages and extracting content."""

    def __init__(self, firecrawl_api_key: str | None = None):
        """
        Initialize the WebCrawlerConnector class.

        Args:
            firecrawl_api_key: Firecrawl API key (optional). If provided, Firecrawl will be tried first
                             and Chromium will be used as fallback if Firecrawl fails. If not provided,
                             Chromium will be used directly.
        """
        self.firecrawl_api_key = firecrawl_api_key
        self.use_firecrawl = bool(firecrawl_api_key)

    def set_api_key(self, api_key: str) -> None:
        """
        Set the Firecrawl API key and enable Firecrawl usage.

        Args:
            api_key: Firecrawl API key
        """
        self.firecrawl_api_key = api_key
        self.use_firecrawl = True

    async def crawl_url(
        self, url: str, formats: list[str] | None = None
    ) -> tuple[dict[str, Any] | None, str | None]:
        """
        Crawl a single URL and extract its content.

        Fallback order:
          1. Firecrawl (if API key configured)
          2. Plain HTTP + Trafilatura (lightweight, no subprocess)
          3. Playwright / Chromium (needs subprocess-capable event loop)

        Args:
            url: URL to crawl
            formats: List of formats to extract (e.g., ["markdown", "html"]) - only for Firecrawl

        Returns:
            Tuple containing (crawl result dict, error message or None)
            Result dict contains:
                - content: Extracted content (markdown or HTML)
                - metadata: Page metadata (title, description, etc.)
                - source: Original URL
                - crawler_type: Type of crawler used
            # Validate URL
        """
        try:
            if not validators.url(url):
                return None, f"Invalid URL: {url}"

            errors: list[str] = []

            # --- 1. Firecrawl (premium, if configured) ---
            if self.use_firecrawl:
                try:
                    logger.info(f"[webcrawler] Using Firecrawl for: {url}")
                    return await self._crawl_with_firecrawl(url, formats), None
                except Exception as exc:
                    errors.append(f"Firecrawl: {exc!s}")
                    logger.warning(
                        f"[webcrawler] Firecrawl failed for {url}: {exc!s}"
                    )

            # --- 2. HTTP + Trafilatura (no subprocess required) ---
            try:
                logger.info(f"[webcrawler] Using HTTP+Trafilatura for: {url}")
                result = await self._crawl_with_http(url)
                if result:
                    return result, None
                errors.append("HTTP+Trafilatura: empty extraction")
            except Exception as exc:
                errors.append(f"HTTP+Trafilatura: {exc!s}")
                logger.warning(
                    f"[webcrawler] HTTP+Trafilatura failed for {url}: {exc!s}"
                )

            # --- 3. Playwright / Chromium (full browser, last resort) ---
            try:
                logger.info(f"[webcrawler] Using Chromium+Trafilatura for: {url}")
                return await self._crawl_with_chromium(url), None
            except NotImplementedError:
                errors.append(
                    "Chromium: event loop does not support subprocesses "
                    "(common on Windows with uvicorn --reload)"
                )
                logger.warning(
                    f"[webcrawler] Chromium unavailable for {url}: "
                    "current event loop does not support subprocesses"
                )
            except Exception as exc:
                errors.append(f"Chromium: {exc!s}")
                logger.warning(f"[webcrawler] Chromium failed for {url}: {exc!s}")

            return None, f"All crawl methods failed for {url}. {'; '.join(errors)}"

        except Exception as e:
            return None, f"Error crawling URL {url}: {e!s}"

    async def _crawl_with_firecrawl(
        self, url: str, formats: list[str] | None = None
    ) -> dict[str, Any]:
        """
        Crawl URL using Firecrawl.

        Args:
            url: URL to crawl
            formats: List of formats to extract

        Returns:
            Dict containing crawled content and metadata

        Raises:
            ValueError: If Firecrawl scraping fails
        """
        if not self.firecrawl_api_key:
            raise ValueError("Firecrawl API key not set. Call set_api_key() first.")

        firecrawl_app = AsyncFirecrawlApp(api_key=self.firecrawl_api_key)

        # Default to markdown format
        if formats is None:
            formats = ["markdown"]

        # v2 API returns Document directly and raises an exception on failure
        scrape_result = await firecrawl_app.scrape(url, formats=formats)

        if not scrape_result:
            raise ValueError("Firecrawl returned no result")

        # Extract content based on format
        content = scrape_result.markdown or scrape_result.html or ""

        # Extract metadata - v2 returns DocumentMetadata object
        metadata_obj = scrape_result.metadata
        metadata = metadata_obj.model_dump() if metadata_obj else {}

        return {
            "content": content,
            "metadata": {
                "source": url,
                "title": metadata.get("title", url),
                "description": metadata.get("description", ""),
                "language": metadata.get("language", ""),
                "sourceURL": metadata.get("source_url", url),
                **metadata,
            },
            "crawler_type": "firecrawl",
        }

    async def _crawl_with_http(self, url: str) -> dict[str, Any] | None:
        """
        Crawl URL using a plain HTTP request + Trafilatura content extraction.

        This method avoids launching a browser subprocess, making it safe to
        call from any asyncio event loop (including Windows SelectorEventLoop
        which does not support ``create_subprocess_exec``).

        Returns ``None`` when Trafilatura cannot extract meaningful content
        (e.g. JS-rendered SPAs) so the caller can fall through to Chromium.
        """
        ua = UserAgent()
        user_agent = ua.random
        proxy_url = get_residential_proxy_url()

        async with httpx.AsyncClient(
            timeout=20.0,
            follow_redirects=True,
            proxy=proxy_url,
            headers={
                "User-Agent": user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
            },
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            raw_html = response.text

        if not raw_html or len(raw_html.strip()) == 0:
            return None

        extracted_content = trafilatura.extract(
            raw_html,
            output_format="markdown",
            include_comments=False,
            include_tables=True,
            include_images=True,
            include_links=True,
        )

        if not extracted_content or len(extracted_content.strip()) == 0:
            return None

        trafilatura_metadata = trafilatura.extract_metadata(raw_html)

        metadata: dict[str, str] = {"source": url}
        if trafilatura_metadata:
            if trafilatura_metadata.title:
                metadata["title"] = trafilatura_metadata.title
            if trafilatura_metadata.description:
                metadata["description"] = trafilatura_metadata.description
            if trafilatura_metadata.author:
                metadata["author"] = trafilatura_metadata.author
            if trafilatura_metadata.date:
                metadata["date"] = trafilatura_metadata.date
        metadata.setdefault("title", url)

        return {
            "content": extracted_content,
            "metadata": metadata,
            "crawler_type": "http",
        }

    async def _crawl_with_chromium(self, url: str) -> dict[str, Any]:
        """
        Crawl URL using Playwright with Trafilatura for content extraction.
        Falls back to raw HTML if Trafilatura extraction fails.

        Runs the sync Playwright API in a thread so it works on any event
        loop, including Windows ``SelectorEventLoop`` which cannot spawn
        subprocesses.

        Args:
            url: URL to crawl

        Returns:
            Dict containing crawled content and metadata

        Raises:
            Exception: If crawling fails
        """
        return await asyncio.to_thread(self._crawl_with_chromium_sync, url)

    def _crawl_with_chromium_sync(self, url: str) -> dict[str, Any]:
        """Synchronous Playwright crawl executed in a worker thread."""
        ua = UserAgent()
        user_agent = ua.random

        playwright_proxy = get_playwright_proxy()

        with sync_playwright() as p:
            launch_kwargs: dict = {"headless": True}
            if playwright_proxy:
                launch_kwargs["proxy"] = playwright_proxy
            browser = p.chromium.launch(**launch_kwargs)
            context = browser.new_context(user_agent=user_agent)
            page = context.new_page()

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                raw_html = page.content()
                page_title = page.title()
            finally:
                browser.close()

        if not raw_html:
            raise ValueError(f"Failed to load content from {url}")

        base_metadata = {"title": page_title} if page_title else {}

        extracted_content = None
        trafilatura_metadata = None

        try:
            extracted_content = trafilatura.extract(
                raw_html,
                output_format="markdown",
                include_comments=False,
                include_tables=True,
                include_images=True,
                include_links=True,
            )

            trafilatura_metadata = trafilatura.extract_metadata(raw_html)

            if not extracted_content or len(extracted_content.strip()) == 0:
                extracted_content = None

        except Exception:
            extracted_content = None

        metadata = {
            "source": url,
            "title": (
                trafilatura_metadata.title
                if trafilatura_metadata and trafilatura_metadata.title
                else base_metadata.get("title", url)
            ),
        }

        if trafilatura_metadata:
            if trafilatura_metadata.description:
                metadata["description"] = trafilatura_metadata.description
            if trafilatura_metadata.author:
                metadata["author"] = trafilatura_metadata.author
            if trafilatura_metadata.date:
                metadata["date"] = trafilatura_metadata.date

        metadata.update(base_metadata)

        return {
            "content": extracted_content if extracted_content else raw_html,
            "metadata": metadata,
            "crawler_type": "chromium",
        }

    def format_to_structured_document(
        self, crawl_result: dict[str, Any], exclude_metadata: bool = False
    ) -> str:
        """
        Format crawl result as a structured document.

        Args:
            crawl_result: Result from crawl_url method
            exclude_metadata: If True, excludes ALL metadata fields from the document.
                            This is useful for content hash generation to ensure the hash
                            only changes when actual content changes, not when metadata
                            (which often contains dynamic fields like timestamps, IDs, etc.) changes.

        Returns:
            Structured document string
        """
        metadata = crawl_result["metadata"]
        content = crawl_result["content"]

        document_parts = ["<DOCUMENT>"]

        # Include metadata section only if not excluded
        if not exclude_metadata:
            document_parts.append("<METADATA>")
            for key, value in metadata.items():
                document_parts.append(f"{key.upper()}: {value}")
            document_parts.append("</METADATA>")

        document_parts.extend(
            [
                "<CONTENT>",
                "FORMAT: markdown",
                "TEXT_START",
                content,
                "TEXT_END",
                "</CONTENT>",
                "</DOCUMENT>",
            ]
        )

        return "\n".join(document_parts)
