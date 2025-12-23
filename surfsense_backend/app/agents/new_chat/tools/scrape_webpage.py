"""
Web scraping tool for the SurfSense agent.

This module provides a tool for scraping and extracting content from webpages
using the existing WebCrawlerConnector. The scraped content can be used by
the agent to answer questions about web pages.
"""

import hashlib
from typing import Any
from urllib.parse import urlparse

from langchain_core.tools import tool

from app.connectors.webcrawler_connector import WebCrawlerConnector


def extract_domain(url: str) -> str:
    """Extract the domain from a URL."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc
        # Remove 'www.' prefix if present
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return ""


def generate_scrape_id(url: str) -> str:
    """Generate a unique ID for a scraped webpage."""
    hash_val = hashlib.md5(url.encode()).hexdigest()[:12]
    return f"scrape-{hash_val}"


def truncate_content(content: str, max_length: int = 50000) -> tuple[str, bool]:
    """
    Truncate content to a maximum length.

    Returns:
        Tuple of (truncated_content, was_truncated)
    """
    if len(content) <= max_length:
        return content, False

    # Try to truncate at a sentence boundary
    truncated = content[:max_length]
    last_period = truncated.rfind(".")
    last_newline = truncated.rfind("\n\n")

    # Use the later of the two boundaries, or just truncate
    boundary = max(last_period, last_newline)
    if boundary > max_length * 0.8:  # Only use boundary if it's not too far back
        truncated = content[: boundary + 1]

    return truncated + "\n\n[Content truncated...]", True


def create_scrape_webpage_tool(firecrawl_api_key: str | None = None):
    """
    Factory function to create the scrape_webpage tool.

    Args:
        firecrawl_api_key: Optional Firecrawl API key for premium web scraping.
                          Falls back to Chromium/Trafilatura if not provided.

    Returns:
        A configured tool function for scraping webpages.
    """

    @tool
    async def scrape_webpage(
        url: str,
        max_length: int = 50000,
    ) -> dict[str, Any]:
        """
        Scrape and extract the main content from a webpage.

        Use this tool when the user wants you to read, summarize, or answer
        questions about a specific webpage's content. This tool actually
        fetches and reads the full page content.

        Common triggers:
        - "Read this article and summarize it"
        - "What does this page say about X?"
        - "Summarize this blog post for me"
        - "Tell me the key points from this article"
        - "What's in this webpage?"

        Args:
            url: The URL of the webpage to scrape (must be HTTP/HTTPS)
            max_length: Maximum content length to return (default: 50000 chars)

        Returns:
            A dictionary containing:
            - id: Unique identifier for this scrape
            - assetId: The URL (for deduplication)
            - kind: "article" (type of content)
            - href: The URL to open when clicked
            - title: Page title
            - description: Brief description or excerpt
            - content: The extracted main content (markdown format)
            - domain: The domain name
            - word_count: Approximate word count
            - was_truncated: Whether content was truncated
            - error: Error message (if scraping failed)
        """
        scrape_id = generate_scrape_id(url)
        domain = extract_domain(url)

        # Validate and normalize URL
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        try:
            # Create webcrawler connector
            connector = WebCrawlerConnector(firecrawl_api_key=firecrawl_api_key)

            # Crawl the URL
            result, error = await connector.crawl_url(url, formats=["markdown"])

            if error:
                return {
                    "id": scrape_id,
                    "assetId": url,
                    "kind": "article",
                    "href": url,
                    "title": domain or "Webpage",
                    "domain": domain,
                    "error": error,
                }

            if not result:
                return {
                    "id": scrape_id,
                    "assetId": url,
                    "kind": "article",
                    "href": url,
                    "title": domain or "Webpage",
                    "domain": domain,
                    "error": "No content returned from crawler",
                }

            # Extract content and metadata
            content = result.get("content", "")
            metadata = result.get("metadata", {})

            # Get title from metadata
            title = metadata.get("title", "")
            if not title:
                title = domain or url.split("/")[-1] or "Webpage"

            # Get description from metadata
            description = metadata.get("description", "")
            if not description and content:
                # Use first paragraph as description
                first_para = content.split("\n\n")[0] if content else ""
                description = (
                    first_para[:300] + "..." if len(first_para) > 300 else first_para
                )

            # Truncate content if needed
            content, was_truncated = truncate_content(content, max_length)

            # Calculate word count
            word_count = len(content.split())

            return {
                "id": scrape_id,
                "assetId": url,
                "kind": "article",
                "href": url,
                "title": title,
                "description": description,
                "content": content,
                "domain": domain,
                "word_count": word_count,
                "was_truncated": was_truncated,
                "crawler_type": result.get("crawler_type", "unknown"),
                "author": metadata.get("author"),
                "date": metadata.get("date"),
            }

        except Exception as e:
            error_message = str(e)
            print(f"[scrape_webpage] Error scraping {url}: {error_message}")
            return {
                "id": scrape_id,
                "assetId": url,
                "kind": "article",
                "href": url,
                "title": domain or "Webpage",
                "domain": domain,
                "error": f"Failed to scrape: {error_message[:100]}",
            }

    return scrape_webpage
