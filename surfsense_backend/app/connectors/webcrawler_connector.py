"""
WebCrawler Connector Module

A module for crawling web pages and extracting content using Firecrawl or Playwright.
Provides a unified interface for web scraping.
"""

import logging
from typing import Any

import trafilatura
import validators
from fake_useragent import UserAgent
from firecrawl import AsyncFirecrawlApp
from playwright.async_api import async_playwright

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

        If Firecrawl API key is provided, tries Firecrawl first and falls back to Chromium
        if Firecrawl fails. If no Firecrawl API key is provided, uses Chromium directly.

        Args:
            url: URL to crawl
            formats: List of formats to extract (e.g., ["markdown", "html"]) - only for Firecrawl

        Returns:
            Tuple containing (crawl result dict, error message or None)
            Result dict contains:
                - content: Extracted content (markdown or HTML)
                - metadata: Page metadata (title, description, etc.)
                - source: Original URL
                - crawler_type: Type of crawler used ("firecrawl" or "chromium")
        """
        try:
            # Validate URL
            if not validators.url(url):
                return None, f"Invalid URL: {url}"

            # Try Firecrawl first if API key is provided
            if self.use_firecrawl:
                try:
                    logger.info(f"[webcrawler] Using Firecrawl for: {url}")
                    result = await self._crawl_with_firecrawl(url, formats)
                    return result, None
                except Exception as firecrawl_error:
                    # Firecrawl failed, fallback to Chromium
                    logger.warning(
                        f"[webcrawler] Firecrawl failed, falling back to Chromium+Trafilatura for: {url}"
                    )
                    try:
                        result = await self._crawl_with_chromium(url)
                        return result, None
                    except Exception as chromium_error:
                        return (
                            None,
                            f"Both Firecrawl and Chromium failed. Firecrawl error: {firecrawl_error!s}, Chromium error: {chromium_error!s}",
                        )
            else:
                # No Firecrawl API key, use Chromium directly
                logger.info(f"[webcrawler] Using Chromium+Trafilatura for: {url}")
                result = await self._crawl_with_chromium(url)
                return result, None

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

    async def _crawl_with_chromium(self, url: str) -> dict[str, Any]:
        """
        Crawl URL using Playwright with Trafilatura for content extraction.
        Falls back to raw HTML if Trafilatura extraction fails.

        Args:
            url: URL to crawl

        Returns:
            Dict containing crawled content and metadata

        Raises:
            Exception: If crawling fails
        """
        # Generate a realistic User-Agent to avoid bot detection
        ua = UserAgent()
        user_agent = ua.random

        # Use Playwright to fetch the page
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(user_agent=user_agent)
            page = await context.new_page()

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                raw_html = await page.content()
                page_title = await page.title()
            finally:
                await browser.close()

        if not raw_html:
            raise ValueError(f"Failed to load content from {url}")

        # Extract basic metadata from the page
        base_metadata = {"title": page_title} if page_title else {}

        # Try to extract main content using Trafilatura
        extracted_content = None
        trafilatura_metadata = None

        try:
            # Extract main content as markdown
            extracted_content = trafilatura.extract(
                raw_html,
                output_format="markdown",  # Get clean markdown
                include_comments=False,  # Exclude comments
                include_tables=True,  # Keep tables
                include_images=True,  # Keep image references
                include_links=True,  # Keep links
            )

            # Extract metadata using Trafilatura
            trafilatura_metadata = trafilatura.extract_metadata(raw_html)

            if not extracted_content or len(extracted_content.strip()) == 0:
                extracted_content = None

        except Exception:
            extracted_content = None

        # Build metadata, preferring Trafilatura metadata when available
        metadata = {
            "source": url,
            "title": (
                trafilatura_metadata.title
                if trafilatura_metadata and trafilatura_metadata.title
                else base_metadata.get("title", url)
            ),
        }

        # Add additional metadata from Trafilatura if available
        if trafilatura_metadata:
            if trafilatura_metadata.description:
                metadata["description"] = trafilatura_metadata.description
            if trafilatura_metadata.author:
                metadata["author"] = trafilatura_metadata.author
            if trafilatura_metadata.date:
                metadata["date"] = trafilatura_metadata.date

        # Add any remaining base metadata
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
