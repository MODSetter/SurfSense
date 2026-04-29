"""Unit tests for ``stream_new_chat._extract_chunk_parts``.

Earlier versions only handled ``isinstance(chunk.content, str)`` and
silently dropped every other shape (Anthropic typed-block lists,
Bedrock reasoning blocks, ``additional_kwargs.reasoning_content`` from
a few providers). These regression tests pin those four shapes plus the
defensive cases (``None`` chunk, mixed types, missing fields).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from app.tasks.chat.stream_new_chat import _extract_chunk_parts


@dataclass
class _FakeChunk:
    """Minimal stand-in for ``AIMessageChunk`` used in unit tests."""

    content: Any = ""
    additional_kwargs: dict[str, Any] = field(default_factory=dict)
    tool_call_chunks: list[dict[str, Any]] = field(default_factory=list)


class TestStringContent:
    def test_plain_string_content_extracts_as_text(self) -> None:
        chunk = _FakeChunk(content="hello world")
        out = _extract_chunk_parts(chunk)
        assert out["text"] == "hello world"
        assert out["reasoning"] == ""
        assert out["tool_call_chunks"] == []

    def test_empty_string_content_yields_empty_text(self) -> None:
        chunk = _FakeChunk(content="")
        out = _extract_chunk_parts(chunk)
        assert out["text"] == ""
        assert out["reasoning"] == ""
        assert out["tool_call_chunks"] == []


class TestListContent:
    def test_list_of_text_blocks_concatenates(self) -> None:
        chunk = _FakeChunk(
            content=[
                {"type": "text", "text": "Hello "},
                {"type": "text", "text": "world"},
            ]
        )
        out = _extract_chunk_parts(chunk)
        assert out["text"] == "Hello world"
        assert out["reasoning"] == ""

    def test_mixed_text_and_reasoning_blocks(self) -> None:
        chunk = _FakeChunk(
            content=[
                {"type": "reasoning", "reasoning": "Let me think... "},
                {"type": "reasoning", "text": "still thinking."},
                {"type": "text", "text": "The answer is 42."},
            ]
        )
        out = _extract_chunk_parts(chunk)
        assert out["text"] == "The answer is 42."
        assert out["reasoning"] == "Let me think... still thinking."

    def test_tool_call_chunks_in_content_list_extracted(self) -> None:
        chunk = _FakeChunk(
            content=[
                {"type": "text", "text": "Calling tool..."},
                {
                    "type": "tool_call_chunk",
                    "id": "call_123",
                    "name": "make_widget",
                    "args": '{"color":"red"}',
                },
            ]
        )
        out = _extract_chunk_parts(chunk)
        assert out["text"] == "Calling tool..."
        assert out["reasoning"] == ""
        assert len(out["tool_call_chunks"]) == 1
        assert out["tool_call_chunks"][0]["id"] == "call_123"
        assert out["tool_call_chunks"][0]["name"] == "make_widget"

    def test_tool_use_blocks_also_extracted(self) -> None:
        """Some providers (Anthropic) emit ``type='tool_use'`` instead."""
        chunk = _FakeChunk(
            content=[
                {
                    "type": "tool_use",
                    "id": "call_xyz",
                    "name": "search",
                },
            ]
        )
        out = _extract_chunk_parts(chunk)
        assert out["tool_call_chunks"] == [
            {"type": "tool_use", "id": "call_xyz", "name": "search"}
        ]

    def test_unknown_block_types_are_ignored(self) -> None:
        chunk = _FakeChunk(
            content=[
                {"type": "image_url", "url": "https://example.com/x.png"},
                {"type": "text", "text": "ok"},
            ]
        )
        out = _extract_chunk_parts(chunk)
        assert out["text"] == "ok"

    def test_blocks_without_text_field_are_ignored(self) -> None:
        chunk = _FakeChunk(
            content=[
                {"type": "text"},  # no text/content key
                {"type": "text", "text": "kept"},
            ]
        )
        out = _extract_chunk_parts(chunk)
        assert out["text"] == "kept"


class TestAdditionalKwargsReasoning:
    def test_reasoning_content_in_additional_kwargs(self) -> None:
        """Some providers stash reasoning in ``additional_kwargs.reasoning_content``."""
        chunk = _FakeChunk(
            content="visible answer",
            additional_kwargs={"reasoning_content": "internal monologue"},
        )
        out = _extract_chunk_parts(chunk)
        assert out["text"] == "visible answer"
        assert out["reasoning"] == "internal monologue"

    def test_reasoning_appended_to_typed_block_reasoning(self) -> None:
        chunk = _FakeChunk(
            content=[{"type": "reasoning", "text": "from blocks. "}],
            additional_kwargs={"reasoning_content": "from kwargs."},
        )
        out = _extract_chunk_parts(chunk)
        assert out["reasoning"] == "from blocks. from kwargs."


class TestToolCallChunksAttribute:
    def test_tool_call_chunks_attribute_extracted_alongside_string_content(
        self,
    ) -> None:
        chunk = _FakeChunk(
            content="streaming text",
            tool_call_chunks=[
                {"name": "save_document", "args": '{"title":"x"}', "id": "tc-9"}
            ],
        )
        out = _extract_chunk_parts(chunk)
        assert out["text"] == "streaming text"
        assert len(out["tool_call_chunks"]) == 1
        assert out["tool_call_chunks"][0]["id"] == "tc-9"

    def test_attribute_and_typed_block_chunks_both_collected(self) -> None:
        chunk = _FakeChunk(
            content=[
                {
                    "type": "tool_call_chunk",
                    "id": "from-block",
                    "name": "x",
                }
            ],
            tool_call_chunks=[{"id": "from-attr", "name": "y"}],
        )
        out = _extract_chunk_parts(chunk)
        ids = [tcc.get("id") for tcc in out["tool_call_chunks"]]
        assert ids == ["from-block", "from-attr"]


class TestDefensive:
    @pytest.mark.parametrize(
        "chunk_value",
        [None, _FakeChunk(content=None), _FakeChunk(content=42)],
    )
    def test_invalid_chunk_returns_empty_parts(self, chunk_value: Any) -> None:
        out = _extract_chunk_parts(chunk_value)
        assert out["text"] == ""
        assert out["reasoning"] == ""
        assert out["tool_call_chunks"] == []
