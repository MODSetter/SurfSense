"""
WebCrawler Connector Module

A module for crawling web pages and extracting content using Firecrawl or AsyncChromiumLoader.
Provides a unified interface for web scraping.
"""

from typing import Any

import validators
from firecrawl import AsyncFirecrawlApp
from langchain_community.document_loaders import AsyncChromiumLoader


class WebCrawlerConnector:
    """Class for crawling web pages and extracting content."""

    def __init__(self, firecrawl_api_key: str | None = None):
        """
        Initialize the WebCrawlerConnector class.

        Args:
            firecrawl_api_key: Firecrawl API key (optional, will use AsyncChromiumLoader if not provided)
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
        try:
            # Validate URL
            if not validators.url(url):
                return None, f"Invalid URL: {url}"

            if self.use_firecrawl:
                result = await self._crawl_with_firecrawl(url, formats)
            else:
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

        scrape_result = await firecrawl_app.scrape_url(url=url, formats=formats)

        if not scrape_result or not scrape_result.success:
            error_msg = (
                scrape_result.error
                if scrape_result and hasattr(scrape_result, "error")
                else "Unknown error"
            )
            raise ValueError(f"Firecrawl failed to scrape URL: {error_msg}")

        # Extract content based on format
        content = scrape_result.markdown or scrape_result.html or ""
        
        # Extract metadata
        metadata = scrape_result.metadata if scrape_result.metadata else {}

        return {
            "content": content,
            "metadata": {
                "source": url,
                "title": metadata.get("title", url),
                "description": metadata.get("description", ""),
                "language": metadata.get("language", ""),
                "sourceURL": metadata.get("sourceURL", url),
                **metadata,
            },
            "crawler_type": "firecrawl",
        }

    async def _crawl_with_chromium(self, url: str) -> dict[str, Any]:
        """
        Crawl URL using AsyncChromiumLoader.

        Args:
            url: URL to crawl

        Returns:
            Dict containing crawled content and metadata

        Raises:
            Exception: If crawling fails
        """
        crawl_loader = AsyncChromiumLoader(urls=[url], headless=True)
        documents = await crawl_loader.aload()

        if not documents:
            raise ValueError(f"Failed to load content from {url}")

        doc = documents[0]

        # Extract basic metadata from the document
        metadata = doc.metadata if doc.metadata else {}

        return {
            "content": doc.page_content,
            "metadata": {
                "source": url,
                "title": metadata.get("title", url),
                **metadata,
            },
            "crawler_type": "chromium",
        }

    def format_to_structured_document(self, crawl_result: dict[str, Any]) -> str:
        """
        Format crawl result as a structured document.

        Args:
            crawl_result: Result from crawl_url method

        Returns:
            Structured document string
        """
        metadata = crawl_result["metadata"]
        content = crawl_result["content"]

        document_parts = ["<DOCUMENT>", "<METADATA>"]

        # Add all metadata fields
        for key, value in metadata.items():
            document_parts.append(f"{key.upper()}: {value}")

        document_parts.extend(
            [
                "</METADATA>",
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
