"""Unit tests for extracting text from LLM memory responses."""

import pytest

from app.services.memory import MemoryScope, save_memory
from app.utils.content_utils import extract_text_content

pytestmark = pytest.mark.unit


def test_extract_text_content_keeps_no_update_bare_string_from_content_blocks() -> None:
    content = [
        {"type": "thinking", "thinking": "No"},
        {"type": "thinking", "thinking": " memorizable info."},
        "NO_UPDATE",
    ]

    assert extract_text_content(content).strip() == "NO_UPDATE"


def test_extract_text_content_ignores_thinking_blocks_and_keeps_markdown_text() -> None:
    markdown = (
        "## Work Context\n"
        "- (2026-05-02) [fact] Anish is hardening SurfSense memory extraction.\n"
    )
    content = [
        {"type": "thinking", "thinking": "This is durable context."},
        {"type": "text", "text": markdown},
    ]

    assert extract_text_content(content).strip() == markdown.strip()


def test_extract_text_content_returns_empty_when_only_thinking_blocks_are_present() -> (
    None
):
    content = [
        {"type": "thinking", "thinking": "No durable fact."},
        {"type": "thinking", "thinking": "Return no update."},
    ]

    assert extract_text_content(content) == ""


def test_extract_text_content_preserves_plain_string_responses() -> None:
    markdown = (
        "## Preferences\n"
        "- (2026-05-02) [pref] Anish prefers no regex for memory validation.\n"
    )

    assert extract_text_content(markdown) == markdown


@pytest.mark.asyncio
async def test_save_memory_rejects_non_string_payload_before_commit() -> None:
    result = await save_memory(
        scope=MemoryScope.USER,
        target_id="00000000-0000-0000-0000-000000000000",
        content=["NO_UPDATE"],  # type: ignore[arg-type]
        session=None,  # type: ignore[arg-type]
    )

    assert result.status == "error"
    assert "must be a string" in result.message
