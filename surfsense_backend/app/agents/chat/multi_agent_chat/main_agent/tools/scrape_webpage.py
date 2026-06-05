"""
Web scraping tool for the SurfSense agent.

This module provides a tool for scraping and extracting content from webpages
using the existing WebCrawlerConnector. For YouTube URLs, it fetches the
transcript directly via the YouTubeTranscriptApi instead of crawling the page.
"""

import hashlib
import logging
from typing import Any
from urllib.parse import urlparse

import aiohttp
from fake_useragent import UserAgent
from langchain_core.tools import tool
from requests import Session
from youtube_transcript_api import YouTubeTranscriptApi

from app.connectors.webcrawler_connector import WebCrawlerConnector
from app.tasks.document_processors.youtube_processor import get_youtube_video_id
from app.utils.proxy_config import get_requests_proxies

logger = logging.getLogger(__name__)


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


async def _scrape_youtube_video(
    url: str, video_id: str, max_length: int
) -> dict[str, Any]:
    """
    Fetch YouTube video metadata and transcript via the YouTubeTranscriptApi.

    Returns a result dict in the same shape as the regular scrape_webpage output.
    """
    scrape_id = generate_scrape_id(url)
    domain = "youtube.com"

    # --- Video metadata via oEmbed ---
    residential_proxies = get_requests_proxies()

    params = {
        "format": "json",
        "url": f"https://www.youtube.com/watch?v={video_id}",
    }
    oembed_url = "https://www.youtube.com/oembed"

    try:
        async with (
            aiohttp.ClientSession() as http_session,
            http_session.get(
                oembed_url,
                params=params,
                proxy=residential_proxies["http"] if residential_proxies else None,
            ) as response,
        ):
            video_data = await response.json()
    except Exception:
        video_data = {}

    title = video_data.get("title", "YouTube Video")
    author = video_data.get("author_name", "Unknown")

    # --- Transcript via YouTubeTranscriptApi ---
    try:
        ua = UserAgent()
        http_client = Session()
        http_client.headers.update({"User-Agent": ua.random})
        if residential_proxies:
            http_client.proxies.update(residential_proxies)
        ytt_api = YouTubeTranscriptApi(http_client=http_client)

        # List all available transcripts and pick the first one
        # (the video's primary language) instead of defaulting to English
        transcript_list = ytt_api.list(video_id)
        transcript = next(iter(transcript_list))
        captions = transcript.fetch()

        logger.info(
            f"[scrape_webpage] Fetched transcript for {video_id} "
            f"in {transcript.language} ({transcript.language_code})"
        )

        transcript_segments = []
        for line in captions:
            start_time = line.start
            duration = line.duration
            text = line.text
            timestamp = f"[{start_time:.2f}s-{start_time + duration:.2f}s]"
            transcript_segments.append(f"{timestamp} {text}")
        transcript_text = "\n".join(transcript_segments)
    except Exception as e:
        logger.warning(f"[scrape_webpage] No transcript for video {video_id}: {e}")
        transcript_text = f"No captions available for this video. Error: {e!s}"

    # Build combined content
    content = f"# {title}\n\n**Author:** {author}\n**Video ID:** {video_id}\n\n## Transcript\n\n{transcript_text}"

    # Truncate if needed
    content, was_truncated = truncate_content(content, max_length)
    word_count = len(content.split())

    description = f"YouTube video by {author}"

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
        "crawler_type": "youtube_transcript",
        "author": author,
    }


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
        fetches and reads the full page content. For YouTube video URLs it
        fetches the transcript directly instead of crawling the page.

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
            # Check if this is a YouTube URL and use transcript API instead
            video_id = get_youtube_video_id(url)
            if video_id:
                return await _scrape_youtube_video(url, video_id, max_length)

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
            logger.error(f"[scrape_webpage] Error scraping {url}: {error_message}")
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
