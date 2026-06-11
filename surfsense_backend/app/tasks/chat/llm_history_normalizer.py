"""Convert persisted chat content into provider-safe LangChain history.

Assistant UI parts are a UI/storage shape, not an LLM prompt shape. This module
extracts only model-safe content before prior turns are replayed to a provider.
"""

from __future__ import annotations

from typing import Any

_USER_CONTENT_TYPES = {"text", "image", "image_url"}


def _text_from_block(block: dict[str, Any]) -> str:
    value = block.get("text") or block.get("content") or ""
    return value if isinstance(value, str) else ""


def assistant_content_to_llm_text(content: Any) -> str:
    """Return visible assistant text, dropping reasoning/UI/provider blocks."""
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        return _text_from_block(content)
    if not isinstance(content, list):
        return ""

    text_chunks: list[str] = []
    for block in content:
        if isinstance(block, str):
            if block:
                text_chunks.append(block)
            continue
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text":
            text = _text_from_block(block)
            if text:
                text_chunks.append(text)
    return "\n".join(text_chunks)


def user_content_to_llm_content(
    content: Any,
    *,
    allow_images: bool = True,
) -> str | list[dict[str, Any]]:
    """Return provider-safe user text/image content for LangChain."""
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        return _text_from_block(content)
    if not isinstance(content, list):
        return ""

    parts: list[dict[str, Any]] = []
    text_chunks: list[str] = []
    for block in content:
        if isinstance(block, str):
            if block:
                text_chunks.append(block)
            continue
        if not isinstance(block, dict):
            continue
        block_type = block.get("type")
        if block_type not in _USER_CONTENT_TYPES:
            continue
        if block_type == "text":
            text = _text_from_block(block)
            if text:
                parts.append({"type": "text", "text": text})
                text_chunks.append(text)
        elif allow_images and block_type == "image":
            image = block.get("image")
            if isinstance(image, str) and image.startswith("data:"):
                parts.append({"type": "image_url", "image_url": {"url": image}})
        elif allow_images and block_type == "image_url":
            image_url = block.get("image_url")
            if isinstance(image_url, dict):
                url = image_url.get("url")
                if isinstance(url, str) and url.startswith("data:"):
                    parts.append({"type": "image_url", "image_url": {"url": url}})
            elif isinstance(image_url, str) and image_url.startswith("data:"):
                parts.append({"type": "image_url", "image_url": {"url": image_url}})

    if allow_images and any(part.get("type") == "image_url" for part in parts):
        return parts
    return "\n".join(text_chunks)

