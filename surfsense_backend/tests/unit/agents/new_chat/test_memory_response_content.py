"""Unit tests for extracting text from LLM memory responses."""

import pytest

from app.agents.new_chat.tools.update_memory import _save_memory
from app.utils.content_utils import extract_text_content

pytestmark = pytest.mark.unit


class _Recorder:
    def __init__(self) -> None:
        self.applied_content: str | None = None
        self.commit_calls = 0
        self.rollback_calls = 0

    def apply(self, content: str) -> None:
        self.applied_content = content

    async def commit(self) -> None:
        self.commit_calls += 1

    async def rollback(self) -> None:
        self.rollback_calls += 1


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


def test_extract_text_content_returns_empty_when_only_thinking_blocks_are_present() -> None:
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
    recorder = _Recorder()

    result = await _save_memory(
        updated_memory=["NO_UPDATE"],  # type: ignore[arg-type]
        old_memory=None,
        llm=None,
        apply_fn=recorder.apply,
        commit_fn=recorder.commit,
        rollback_fn=recorder.rollback,
        label="memory",
        scope="user",
    )

    assert result["status"] == "error"
    assert "must be a string" in result["message"]
    assert recorder.applied_content is None
    assert recorder.commit_calls == 0
    assert recorder.rollback_calls == 0
