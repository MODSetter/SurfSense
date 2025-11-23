import logging
from typing import Any

import httpx

from app.config import config

logger = logging.getLogger(__name__)


async def convert_markdown_to_blocknote(markdown: str) -> dict[str, Any] | None:
    """
    Convert markdown to BlockNote JSON via Next.js API.

    Args:
        markdown: Markdown string to convert

    Returns:
        BlockNote document as dict, or None if conversion fails
    """
    if not markdown or not markdown.strip():
        logger.warning("Empty markdown provided for conversion")
        return None

    if not markdown or len(markdown) < 10:
        logger.warning("Markdown became too short after sanitization")
        # Return a minimal BlockNote document
        return [
            {
                "type": "paragraph",
                "content": [
                    {
                        "type": "text",
                        "text": "Document content could not be converted for editing.",
                        "styles": {},
                    }
                ],
                "children": [],
            }
        ]

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{config.NEXT_FRONTEND_URL}/api/convert-to-blocknote",
                json={"markdown": markdown},
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
            blocknote_document = data.get("blocknote_document")

            if blocknote_document:
                logger.info(
                    f"Successfully converted markdown to BlockNote (original: {len(markdown)} chars, sanitized: {len(markdown)} chars)"
                )
                return blocknote_document
            else:
                logger.warning("Next.js API returned empty blocknote_document")
                return None

        except httpx.TimeoutException:
            logger.error("Timeout converting markdown to BlockNote after 30s")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error converting markdown to BlockNote: {e.response.status_code} - {e.response.text}"
            )
            # Log first 1000 chars of problematic markdown for debugging
            logger.debug(f"Problematic markdown sample: {markdown[:1000]}")
            return None
        except Exception as e:
            logger.error(f"Failed to convert markdown to BlockNote: {e}", exc_info=True)
            return None


async def convert_blocknote_to_markdown(
    blocknote_document: dict[str, Any] | list[dict[str, Any]],
) -> str | None:
    """
    Convert BlockNote JSON to markdown via Next.js API.

    Args:
        blocknote_document: BlockNote document as dict or list of blocks

    Returns:
        Markdown string, or None if conversion fails
    """
    if not blocknote_document:
        logger.warning("Empty BlockNote document provided for conversion")
        return None

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{config.NEXT_FRONTEND_URL}/api/convert-to-markdown",
                json={"blocknote_document": blocknote_document},
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
            markdown = data.get("markdown")

            if markdown:
                logger.info(
                    f"Successfully converted BlockNote to markdown ({len(markdown)} chars)"
                )
                return markdown
            else:
                logger.warning("Next.js API returned empty markdown")
                return None

        except httpx.TimeoutException:
            logger.error("Timeout converting BlockNote to markdown after 30s")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error converting BlockNote to markdown: {e.response.status_code} - {e.response.text}"
            )
            return None
        except Exception as e:
            logger.error(f"Failed to convert BlockNote to markdown: {e}", exc_info=True)
            return None
