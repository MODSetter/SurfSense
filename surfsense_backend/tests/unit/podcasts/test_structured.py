"""Parsing a model's reply into a structured shape.

Agent LLMs wrap JSON in prose and markdown fences. ``invoke_json`` exists so
every generation node tolerates that the same way. The LLM is an external
boundary, so it is faked with a canned reply; the behavior under test is the
parsing, not the model.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from app.podcasts.generation.structured import StructuredOutputError, invoke_json

pytestmark = pytest.mark.unit


class _Shape(BaseModel):
    name: str
    count: int


class _CannedLLM:
    """A TTS-free stand-in for the chat model: replies with one fixed string."""

    def __init__(self, reply: str) -> None:
        self._reply = reply

    async def ainvoke(self, _messages):
        return SimpleReply(self._reply)


class SimpleReply:
    def __init__(self, content: str) -> None:
        self.content = content


async def _parse(reply: str) -> _Shape:
    return await invoke_json(_CannedLLM(reply), [], _Shape)


async def test_parses_a_clean_json_reply():
    shape = await _parse('{"name": "alpha", "count": 3}')
    assert shape == _Shape(name="alpha", count=3)


async def test_parses_json_wrapped_in_a_markdown_fence():
    reply = '```json\n{"name": "beta", "count": 7}\n```'
    shape = await _parse(reply)
    assert shape == _Shape(name="beta", count=7)


async def test_extracts_json_embedded_in_prose():
    """Reasoning models prepend/append chatter around the object."""
    reply = 'Sure, here you go: {"name": "gamma", "count": 1} — hope that helps!'
    shape = await _parse(reply)
    assert shape == _Shape(name="gamma", count=1)


async def test_raises_when_there_is_no_json_object():
    with pytest.raises(StructuredOutputError):
        await _parse("I could not produce that.")


async def test_raises_when_the_json_does_not_match_the_shape():
    with pytest.raises(StructuredOutputError):
        await _parse('{"name": "delta"}')
