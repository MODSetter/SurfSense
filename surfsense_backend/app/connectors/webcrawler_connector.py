"""
WebCrawler Connector Module

A module for crawling web pages and extracting content using Firecrawl or
Scrapling's tiered fetchers, with Trafilatura for HTML -> markdown extraction.
Provides a unified interface for web scraping.

Fallback order:
  1. Firecrawl                 (if API key is configured)
  2. Scrapling AsyncFetcher    (fast static HTTP, no browser subprocess)
  3. Scrapling DynamicFetcher  (full browser, run in a thread)
  4. Scrapling StealthyFetcher (anti-bot stealth browser, run in a thread)
"""

import asyncio
import logging
import time
from typing import Any

import trafilatura
import validators
from firecrawl import AsyncFirecrawlApp
from scrapling.fetchers import AsyncFetcher, DynamicFetcher, StealthyFetcher

from app.utils.proxy import get_proxy_url

logger = logging.getLogger(__name__)

# Prefix for performance/timing log lines so they are easy to grep/filter.
_PERF = "[webcrawler][perf]"


class WebCrawlerConnector:
    """Class for crawling web pages and extracting content."""

    def __init__(self, firecrawl_api_key: str | None = None):
        """
        Initialize the WebCrawlerConnector class.

        Args:
            firecrawl_api_key: Firecrawl API key (optional). If provided, Firecrawl will be tried first
                             and Scrapling will be used as fallback if Firecrawl fails. If not provided,
                             Scrapling fetchers are used directly.
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
          2. Scrapling AsyncFetcher (fast static HTTP, no subprocess)
          3. Scrapling DynamicFetcher (full browser, run in a thread)
          4. Scrapling StealthyFetcher (anti-bot stealth browser, run in a thread)

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
        """
        total_start = time.perf_counter()
        try:
            if not validators.url(url):
                return None, f"Invalid URL: {url}"

            errors: list[str] = []

            # --- 1. Firecrawl (premium, if configured) ---
            if self.use_firecrawl:
                tier_start = time.perf_counter()
                try:
                    logger.info(f"[webcrawler] Using Firecrawl for: {url}")
                    result = await self._crawl_with_firecrawl(url, formats)
                    self._log_tier_outcome("firecrawl", url, tier_start, "success")
                    self._log_total(url, "firecrawl", total_start)
                    return result, None
                except Exception as exc:
                    errors.append(f"Firecrawl: {exc!s}")
                    self._log_tier_outcome("firecrawl", url, tier_start, "error", exc)

            # --- 2. Scrapling AsyncFetcher (fast static HTTP) ---
            tier_start = time.perf_counter()
            try:
                logger.info(f"[webcrawler] Using Scrapling AsyncFetcher for: {url}")
                result = await self._crawl_with_async_fetcher(url)
                if result:
                    self._log_tier_outcome(
                        "scrapling-static", url, tier_start, "success"
                    )
                    self._log_total(url, "scrapling-static", total_start)
                    return result, None
                errors.append("Scrapling static: empty extraction")
                self._log_tier_outcome("scrapling-static", url, tier_start, "empty")
            except Exception as exc:
                errors.append(f"Scrapling static: {exc!s}")
                self._log_tier_outcome(
                    "scrapling-static", url, tier_start, "error", exc
                )

            # --- 3. Scrapling DynamicFetcher (full browser) ---
            tier_start = time.perf_counter()
            try:
                logger.info(f"[webcrawler] Using Scrapling DynamicFetcher for: {url}")
                result = await self._crawl_with_dynamic(url)
                if result:
                    self._log_tier_outcome(
                        "scrapling-dynamic", url, tier_start, "success"
                    )
                    self._log_total(url, "scrapling-dynamic", total_start)
                    return result, None
                errors.append("Scrapling dynamic: empty extraction")
                self._log_tier_outcome("scrapling-dynamic", url, tier_start, "empty")
            except NotImplementedError:
                errors.append(
                    "Scrapling dynamic: event loop does not support subprocesses "
                    "(common on Windows with uvicorn --reload)"
                )
                self._log_tier_outcome(
                    "scrapling-dynamic", url, tier_start, "unavailable"
                )
            except Exception as exc:
                errors.append(f"Scrapling dynamic: {exc!s}")
                self._log_tier_outcome(
                    "scrapling-dynamic", url, tier_start, "error", exc
                )

            # --- 4. Scrapling StealthyFetcher (anti-bot, last resort) ---
            tier_start = time.perf_counter()
            try:
                logger.info(f"[webcrawler] Using Scrapling StealthyFetcher for: {url}")
                result = await self._crawl_with_stealthy(url)
                if result:
                    self._log_tier_outcome(
                        "scrapling-stealthy", url, tier_start, "success"
                    )
                    self._log_total(url, "scrapling-stealthy", total_start)
                    return result, None
                errors.append("Scrapling stealthy: empty extraction")
                self._log_tier_outcome("scrapling-stealthy", url, tier_start, "empty")
            except NotImplementedError:
                errors.append(
                    "Scrapling stealthy: event loop does not support subprocesses "
                    "(common on Windows with uvicorn --reload)"
                )
                self._log_tier_outcome(
                    "scrapling-stealthy", url, tier_start, "unavailable"
                )
            except Exception as exc:
                errors.append(f"Scrapling stealthy: {exc!s}")
                self._log_tier_outcome(
                    "scrapling-stealthy", url, tier_start, "error", exc
                )

            self._log_total(url, "none", total_start)
            return None, f"All crawl methods failed for {url}. {'; '.join(errors)}"

        except Exception as e:
            self._log_total(url, "error", total_start)
            return None, f"Error crawling URL {url}: {e!s}"

    @staticmethod
    def _log_tier_outcome(
        tier: str,
        url: str,
        tier_start: float,
        outcome: str,
        exc: Exception | None = None,
    ) -> None:
        """Log how long a single tier took and how it ended."""
        elapsed_ms = (time.perf_counter() - tier_start) * 1000
        if outcome == "error":
            logger.warning(
                "%s tier=%s url=%s elapsed_ms=%.1f outcome=error error=%s",
                _PERF,
                tier,
                url,
                elapsed_ms,
                exc,
            )
        else:
            logger.info(
                "%s tier=%s url=%s elapsed_ms=%.1f outcome=%s",
                _PERF,
                tier,
                url,
                elapsed_ms,
                outcome,
            )

    @staticmethod
    def _log_total(url: str, selected: str, total_start: float) -> None:
        """Log the total time spent across all attempted tiers."""
        total_ms = (time.perf_counter() - total_start) * 1000
        logger.info(
            "%s url=%s selected=%s total_ms=%.1f",
            _PERF,
            url,
            selected,
            total_ms,
        )

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

    async def _crawl_with_async_fetcher(self, url: str) -> dict[str, Any] | None:
        """
        Crawl URL using Scrapling's AsyncFetcher (static HTTP) + Trafilatura.

        AsyncFetcher is httpx/curl_cffi based and does not launch a browser
        subprocess, making it safe to call from any asyncio event loop. Returns
        ``None`` when Trafilatura cannot extract meaningful content (e.g. JS
        rendered SPAs) so the caller can fall through to the browser tiers.
        """
        fetch_start = time.perf_counter()
        page = await AsyncFetcher.get(
            url,
            stealthy_headers=True,
            proxy=get_proxy_url(),
            timeout=20,
        )
        fetch_ms = (time.perf_counter() - fetch_start) * 1000

        status = getattr(page, "status", None)
        if status is not None and status >= 400:
            logger.info(
                "%s tier=scrapling-static url=%s fetch_ms=%.1f status=%s outcome=http_error",
                _PERF,
                url,
                fetch_ms,
                status,
            )
            return None

        return self._build_result(
            page.html_content,
            url,
            "scrapling-static",
            allow_raw_fallback=False,
            fetch_ms=fetch_ms,
            status=status,
        )

    async def _crawl_with_dynamic(self, url: str) -> dict[str, Any] | None:
        """
        Crawl URL using Scrapling's DynamicFetcher (full browser) + Trafilatura.

        Runs the sync fetch in a worker thread so it works on any event loop,
        including Windows ``SelectorEventLoop`` which cannot spawn subprocesses.
        """
        return await asyncio.to_thread(self._crawl_with_dynamic_sync, url)

    def _crawl_with_dynamic_sync(self, url: str) -> dict[str, Any] | None:
        """Synchronous DynamicFetcher crawl executed in a worker thread."""
        fetch_start = time.perf_counter()
        page = DynamicFetcher.fetch(
            url,
            headless=True,
            network_idle=True,
            timeout=30000,
            proxy=get_proxy_url(),
        )
        fetch_ms = (time.perf_counter() - fetch_start) * 1000
        return self._build_result(
            page.html_content,
            url,
            "scrapling-dynamic",
            allow_raw_fallback=False,
            fetch_ms=fetch_ms,
            status=getattr(page, "status", None),
        )

    async def _crawl_with_stealthy(self, url: str) -> dict[str, Any] | None:
        """
        Crawl URL using Scrapling's StealthyFetcher (Camoufox) + Trafilatura.

        Last-resort tier with anti-bot features. Runs the sync fetch in a worker
        thread for the same event-loop-safety reasons as DynamicFetcher. Falls
        back to the raw HTML when Trafilatura extraction is empty.
        """
        return await asyncio.to_thread(self._crawl_with_stealthy_sync, url)

    def _crawl_with_stealthy_sync(self, url: str) -> dict[str, Any] | None:
        """Synchronous StealthyFetcher crawl executed in a worker thread."""
        fetch_start = time.perf_counter()
        page = StealthyFetcher.fetch(
            url,
            headless=True,
            network_idle=True,
            block_ads=True,
            proxy=get_proxy_url(),
        )
        fetch_ms = (time.perf_counter() - fetch_start) * 1000
        return self._build_result(
            page.html_content,
            url,
            "scrapling-stealthy",
            allow_raw_fallback=True,
            fetch_ms=fetch_ms,
            status=getattr(page, "status", None),
        )

    def _build_result(
        self,
        raw_html: str | None,
        url: str,
        crawler_type: str,
        *,
        allow_raw_fallback: bool,
        fetch_ms: float | None = None,
        status: int | None = None,
    ) -> dict[str, Any] | None:
        """
        Extract markdown + metadata from raw HTML using Trafilatura.

        Args:
            raw_html: Raw HTML source from a fetcher.
            url: Original URL (used as the metadata source/title fallback).
            crawler_type: Identifier of the tier that produced the HTML.
            allow_raw_fallback: When True, return the raw HTML as content if
                Trafilatura cannot extract anything (used by the last-resort
                stealthy tier). When False, return ``None`` so the caller can
                fall through to the next tier.
            fetch_ms: Time spent fetching the page (for perf logging).
            status: HTTP status code returned by the fetcher (for perf logging).

        Returns:
            Result dict (content/metadata/crawler_type) or ``None``.
        """
        html_len = len(raw_html) if raw_html else 0

        if not raw_html or len(raw_html.strip()) == 0:
            self._log_build(
                crawler_type, url, fetch_ms, 0.0, status, html_len, 0, "empty_html"
            )
            return None

        extract_start = time.perf_counter()
        extracted_content: str | None = None
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

            if extracted_content and len(extracted_content.strip()) == 0:
                extracted_content = None
        except Exception:
            extracted_content = None

        extract_ms = (time.perf_counter() - extract_start) * 1000

        if not extracted_content and not allow_raw_fallback:
            self._log_build(
                crawler_type,
                url,
                fetch_ms,
                extract_ms,
                status,
                html_len,
                0,
                "no_extraction",
            )
            return None

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

        content = extracted_content if extracted_content else raw_html
        self._log_build(
            crawler_type,
            url,
            fetch_ms,
            extract_ms,
            status,
            html_len,
            len(content),
            "extracted" if extracted_content else "raw_fallback",
        )

        return {
            "content": content,
            "metadata": metadata,
            "crawler_type": crawler_type,
        }

    @staticmethod
    def _log_build(
        crawler_type: str,
        url: str,
        fetch_ms: float | None,
        extract_ms: float,
        status: int | None,
        html_len: int,
        content_len: int,
        outcome: str,
    ) -> None:
        """Emit a detailed perf line splitting fetch vs Trafilatura extraction."""
        fetch_repr = f"{fetch_ms:.1f}" if fetch_ms is not None else "n/a"
        logger.info(
            "%s tier=%s url=%s status=%s fetch_ms=%s extract_ms=%.1f "
            "html_len=%d content_len=%d outcome=%s",
            _PERF,
            crawler_type,
            url,
            status,
            fetch_repr,
            extract_ms,
            html_len,
            content_len,
            outcome,
        )

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
