"""
Link preview tool for the SurfSense agent.

This module provides a tool for fetching URL metadata (title, description,
Open Graph image, etc.) to display rich link previews in the chat UI.
"""

import hashlib
import re
from typing import Any
from urllib.parse import urlparse

import httpx
from langchain_core.tools import tool


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


def extract_og_content(html: str, property_name: str) -> str | None:
    """Extract Open Graph meta content from HTML."""
    # Try og:property first
    pattern = rf'<meta[^>]+property=["\']og:{property_name}["\'][^>]+content=["\']([^"\']+)["\']'
    match = re.search(pattern, html, re.IGNORECASE)
    if match:
        return match.group(1)

    # Try content before property
    pattern = rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:{property_name}["\']'
    match = re.search(pattern, html, re.IGNORECASE)
    if match:
        return match.group(1)

    return None


def extract_twitter_content(html: str, name: str) -> str | None:
    """Extract Twitter Card meta content from HTML."""
    pattern = (
        rf'<meta[^>]+name=["\']twitter:{name}["\'][^>]+content=["\']([^"\']+)["\']'
    )
    match = re.search(pattern, html, re.IGNORECASE)
    if match:
        return match.group(1)

    # Try content before name
    pattern = (
        rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:{name}["\']'
    )
    match = re.search(pattern, html, re.IGNORECASE)
    if match:
        return match.group(1)

    return None


def extract_meta_description(html: str) -> str | None:
    """Extract meta description from HTML."""
    pattern = r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']'
    match = re.search(pattern, html, re.IGNORECASE)
    if match:
        return match.group(1)

    # Try content before name
    pattern = r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']description["\']'
    match = re.search(pattern, html, re.IGNORECASE)
    if match:
        return match.group(1)

    return None


def extract_title(html: str) -> str | None:
    """Extract title from HTML."""
    # Try og:title first
    og_title = extract_og_content(html, "title")
    if og_title:
        return og_title

    # Try twitter:title
    twitter_title = extract_twitter_content(html, "title")
    if twitter_title:
        return twitter_title

    # Fall back to <title> tag
    pattern = r"<title[^>]*>([^<]+)</title>"
    match = re.search(pattern, html, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    return None


def extract_description(html: str) -> str | None:
    """Extract description from HTML."""
    # Try og:description first
    og_desc = extract_og_content(html, "description")
    if og_desc:
        return og_desc

    # Try twitter:description
    twitter_desc = extract_twitter_content(html, "description")
    if twitter_desc:
        return twitter_desc

    # Fall back to meta description
    return extract_meta_description(html)


def extract_image(html: str) -> str | None:
    """Extract image URL from HTML."""
    # Try og:image first
    og_image = extract_og_content(html, "image")
    if og_image:
        return og_image

    # Try twitter:image
    twitter_image = extract_twitter_content(html, "image")
    if twitter_image:
        return twitter_image

    return None


def generate_preview_id(url: str) -> str:
    """Generate a unique ID for a link preview."""
    hash_val = hashlib.md5(url.encode()).hexdigest()[:12]
    return f"link-preview-{hash_val}"


def create_link_preview_tool():
    """
    Factory function to create the link_preview tool.

    Returns:
        A configured tool function for fetching link previews.
    """

    @tool
    async def link_preview(url: str) -> dict[str, Any]:
        """
        Fetch metadata for a URL to display a rich link preview.

        Use this tool when the user shares a URL or asks about a specific webpage.
        This tool fetches the page's Open Graph metadata (title, description, image)
        to display a nice preview card in the chat.

        Common triggers include:
        - User shares a URL in the chat
        - User asks "What's this link about?" or similar
        - User says "Show me a preview of this page"
        - User wants to preview an article or webpage

        Args:
            url: The URL to fetch metadata for. Must be a valid HTTP/HTTPS URL.

        Returns:
            A dictionary containing:
            - id: Unique identifier for this preview
            - assetId: The URL itself (for deduplication)
            - kind: "link" (type of media card)
            - href: The URL to open when clicked
            - title: Page title
            - description: Page description (if available)
            - thumb: Thumbnail/preview image URL (if available)
            - domain: The domain name
            - error: Error message (if fetch failed)
        """
        preview_id = generate_preview_id(url)
        domain = extract_domain(url)

        # Validate URL
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        try:
            async with httpx.AsyncClient(
                timeout=10.0,
                follow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; SurfSenseBot/1.0; +https://surfsense.net)",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                },
            ) as client:
                response = await client.get(url)
                response.raise_for_status()

                # Get content type to ensure it's HTML
                content_type = response.headers.get("content-type", "")
                if "text/html" not in content_type.lower():
                    # Not an HTML page, return basic info
                    return {
                        "id": preview_id,
                        "assetId": url,
                        "kind": "link",
                        "href": url,
                        "title": url.split("/")[-1] or domain,
                        "description": f"File from {domain}",
                        "domain": domain,
                    }

                html = response.text

                # Extract metadata
                title = extract_title(html) or domain
                description = extract_description(html)
                image = extract_image(html)

                # Make sure image URL is absolute
                if image and not image.startswith(("http://", "https://")):
                    if image.startswith("//"):
                        image = f"https:{image}"
                    elif image.startswith("/"):
                        parsed = urlparse(url)
                        image = f"{parsed.scheme}://{parsed.netloc}{image}"

                # Clean up title and description (unescape HTML entities)
                if title:
                    title = (
                        title.replace("&amp;", "&")
                        .replace("&lt;", "<")
                        .replace("&gt;", ">")
                        .replace("&quot;", '"')
                        .replace("&#39;", "'")
                        .replace("&apos;", "'")
                    )
                if description:
                    description = (
                        description.replace("&amp;", "&")
                        .replace("&lt;", "<")
                        .replace("&gt;", ">")
                        .replace("&quot;", '"')
                        .replace("&#39;", "'")
                        .replace("&apos;", "'")
                    )
                    # Truncate long descriptions
                    if len(description) > 200:
                        description = description[:197] + "..."

                return {
                    "id": preview_id,
                    "assetId": url,
                    "kind": "link",
                    "href": url,
                    "title": title,
                    "description": description,
                    "thumb": image,
                    "domain": domain,
                }

        except httpx.TimeoutException:
            return {
                "id": preview_id,
                "assetId": url,
                "kind": "link",
                "href": url,
                "title": domain or "Link",
                "domain": domain,
                "error": "Request timed out",
            }
        except httpx.HTTPStatusError as e:
            return {
                "id": preview_id,
                "assetId": url,
                "kind": "link",
                "href": url,
                "title": domain or "Link",
                "domain": domain,
                "error": f"HTTP {e.response.status_code}",
            }
        except Exception as e:
            error_message = str(e)
            print(f"[link_preview] Error fetching {url}: {error_message}")
            return {
                "id": preview_id,
                "assetId": url,
                "kind": "link",
                "href": url,
                "title": domain or "Link",
                "domain": domain,
                "error": f"Failed to fetch: {error_message[:50]}",
            }

    return link_preview
