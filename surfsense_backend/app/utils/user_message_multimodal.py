"""Helpers for multimodal user turns (text + inline images) in LangChain messages."""

from __future__ import annotations

import base64
import binascii
from typing import Any


def build_human_message_content(
    final_query: str, image_data_urls: list[str]
) -> str | list[dict[str, Any]]:
    if not image_data_urls:
        return final_query
    parts: list[dict[str, Any]] = [{"type": "text", "text": final_query}]
    for url in image_data_urls:
        parts.append({"type": "image_url", "image_url": {"url": url}})
    return parts


def split_langchain_human_content(content: str | list[Any]) -> tuple[str, list[str]]:
    """Return plain text and data URLs from a LangChain HumanMessage ``content`` value."""
    if isinstance(content, str):
        return content, []
    if not isinstance(content, list):
        return "", []

    text_chunks: list[str] = []
    urls: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        btype = block.get("type")
        if btype == "text":
            t = block.get("text")
            if isinstance(t, str) and t:
                text_chunks.append(t)
        elif btype == "image_url":
            iu = block.get("image_url")
            if isinstance(iu, dict):
                u = iu.get("url")
                if isinstance(u, str) and u.startswith("data:"):
                    urls.append(u)
            elif isinstance(iu, str) and iu.startswith("data:"):
                urls.append(iu)
    return "\n".join(text_chunks), urls


def decode_base64_image(data: str, *, max_bytes: int) -> bytes:
    raw = data.strip()
    if not raw:
        raise ValueError("empty image payload")
    try:
        decoded = base64.b64decode(raw, validate=True)
    except binascii.Error as e:
        raise ValueError("invalid base64 image data") from e
    if len(decoded) > max_bytes:
        raise ValueError("image exceeds maximum size")
    return decoded


def to_data_url(media_type: str, raw_b64: str) -> str:
    return f"data:{media_type};base64,{raw_b64.strip()}"


def split_persisted_user_content_parts(parts: list[Any]) -> tuple[str, list[str]]:
    """Extract plain text and data URLs from persisted assistant-ui style user ``content``."""
    text_chunks: list[str] = []
    urls: list[str] = []
    for block in parts:
        if not isinstance(block, dict):
            continue
        btype = block.get("type")
        if btype == "text":
            t = block.get("text")
            if isinstance(t, str):
                text_chunks.append(t)
        elif btype == "image":
            u = block.get("image")
            if isinstance(u, str) and u.startswith("data:"):
                urls.append(u)
    return "".join(text_chunks), urls
