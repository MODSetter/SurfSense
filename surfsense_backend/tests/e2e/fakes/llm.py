"""Deterministic LLM fake for the E2E indexing pipeline.

The production indexing pipeline summarizes documents with:

    summary_chain = SUMMARY_PROMPT_TEMPLATE | llm
    summary_result = await summary_chain.ainvoke({"document": ...})
    summary_content = summary_result.content

The `llm` parameter is supplied per-document by
`app.services.llm_service.get_user_long_context_llm`. We patch THAT
function to return a langchain-native FakeListChatModel so the rest of
the chain works unchanged. No real LLM provider package is touched.

Run-backend / run-celery use unittest.mock.patch.start() to install
this at every binding site (the source module + every consumer that
did `from app.services.llm_service import get_user_long_context_llm`
at module load time).
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.language_models.fake_chat_models import FakeListChatModel

logger = logging.getLogger(__name__)


def _make_fake_llm() -> FakeListChatModel:
    """Build a fresh FakeListChatModel that returns a deterministic summary."""
    # FakeListChatModel cycles through `responses` for each invocation. We
    # supply a single deterministic string. The summary content is tagged
    # with a marker that specs CAN assert on if they want, but the
    # primary indexing assertion is on the file content (chunked + stored
    # separately by the pipeline).
    fake = FakeListChatModel(
        responses=[
            "E2E_FAKE_SUMMARY: Indexed by Playwright E2E run with deterministic LLM stub."
        ]
    )
    return fake


async def fake_get_user_long_context_llm(*args: Any, **kwargs: Any) -> Any:
    """Drop-in replacement for app.services.llm_service.get_user_long_context_llm."""
    logger.info("[fake-llm] returning FakeListChatModel for E2E indexing")
    return _make_fake_llm()
