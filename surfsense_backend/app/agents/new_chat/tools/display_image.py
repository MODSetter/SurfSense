"""
Display image tool for the SurfSense agent.

This module provides a tool for displaying images in the chat UI
with metadata like title, description, and source attribution.
"""

import hashlib
from typing import Any
from urllib.parse import urlparse

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


def generate_image_id(src: str) -> str:
    """Generate a unique ID for an image."""
    hash_val = hashlib.md5(src.encode()).hexdigest()[:12]
    return f"image-{hash_val}"


def create_display_image_tool():
    """
    Factory function to create the display_image tool.

    Returns:
        A configured tool function for displaying images.
    """

    @tool
    async def display_image(
        src: str,
        alt: str = "Image",
        title: str | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:
        """
        Display an image in the chat with metadata.

        Use this tool when you want to show an image to the user.
        This displays the image with an optional title, description,
        and source attribution.

        Common use cases:
        - Showing an image from a URL the user mentioned
        - Displaying a diagram or chart you're referencing
        - Showing example images when explaining concepts

        Args:
            src: The URL of the image to display (must be a valid HTTP/HTTPS URL)
            alt: Alternative text describing the image (for accessibility)
            title: Optional title to display below the image
            description: Optional description providing context about the image

        Returns:
            A dictionary containing image metadata for the UI to render:
            - id: Unique identifier for this image
            - assetId: The image URL (for deduplication)
            - src: The image URL
            - alt: Alt text for accessibility
            - title: Image title (if provided)
            - description: Image description (if provided)
            - domain: Source domain
        """
        image_id = generate_image_id(src)

        # Ensure URL has protocol
        if not src.startswith(("http://", "https://")):
            src = f"https://{src}"

        domain = extract_domain(src)

        # Determine aspect ratio based on common image sources
        ratio = "16:9"  # Default
        if "unsplash.com" in src or "pexels.com" in src:
            ratio = "16:9"
        elif (
            "imgur.com" in src or "github.com" in src or "githubusercontent.com" in src
        ):
            ratio = "auto"

        return {
            "id": image_id,
            "assetId": src,
            "src": src,
            "alt": alt,
            "title": title,
            "description": description,
            "domain": domain,
            "ratio": ratio,
        }

    return display_image
