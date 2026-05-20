"""LLM-backed memory rewrite helpers."""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import HumanMessage

from app.services.memory.prompts import FORCED_REWRITE_PROMPT
from app.services.memory.validation import MEMORY_HARD_LIMIT
from app.utils.content_utils import extract_text_content

logger = logging.getLogger(__name__)


async def forced_rewrite(content: str, llm: Any) -> str | None:
    """Use a focused LLM call to compress memory under the hard limit."""
    try:
        prompt = FORCED_REWRITE_PROMPT.format(
            target=MEMORY_HARD_LIMIT,
            content=content,
        )
        response = await llm.ainvoke(
            [HumanMessage(content=prompt)],
            config={"tags": ["surfsense:internal", "memory-rewrite"]},
        )
        text = extract_text_content(response.content).strip()
        if not text:
            logger.warning("Forced memory rewrite returned empty text")
            return None
        return text
    except Exception:
        logger.exception("Forced memory rewrite LLM call failed")
        return None
