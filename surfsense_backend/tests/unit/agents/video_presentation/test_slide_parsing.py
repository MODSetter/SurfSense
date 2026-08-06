"""Parsing the slide-generation reply.

The video agent used to carry its own copy of the tolerant-parse algorithm and
report failures with ``print``, which dumped the entire model reply — including
the source document it was summarising — into the worker's stdout. It now uses
the shared parser, so these tests pin the tolerance it inherits and the fact
that a failure no longer prints the reply.
"""

from __future__ import annotations

import pytest

from app.agents.video_presentation import nodes
from app.agents.video_presentation.state import PresentationSlides
from app.utils.structured_output import StructuredOutputError, invoke_json

pytestmark = pytest.mark.unit

_SLIDES_JSON = """
{
  "slides": [
    {
      "slide_number": 1,
      "title": "Title",
      "subtitle": "Subtitle",
      "content_in_markdown": "## Heading",
      "speaker_transcripts": ["One sentence."],
      "background_explanation": "Warm and organic"
    }
  ]
}
"""


class _Reply:
    def __init__(self, content: str) -> None:
        self.content = content


class _CannedLLM:
    """Stands in for the chat model with one fixed reply."""

    def __init__(self, reply: str) -> None:
        self._reply = reply

    async def ainvoke(self, _messages):
        return _Reply(self._reply)


async def _parse(reply: str) -> PresentationSlides:
    return await invoke_json(_CannedLLM(reply), [], PresentationSlides)


async def test_parses_a_clean_reply():
    presentation = await _parse(_SLIDES_JSON)
    assert presentation.slides[0].title == "Title"


async def test_parses_a_reply_wrapped_in_a_markdown_fence():
    presentation = await _parse(f"```json\n{_SLIDES_JSON}\n```")
    assert len(presentation.slides) == 1


async def test_parses_a_reply_wrapped_in_prose():
    """Reasoning models narrate before and after the object."""
    presentation = await _parse(
        f"Here are the slides you asked for:\n{_SLIDES_JSON}\nHope that helps."
    )
    assert len(presentation.slides) == 1


async def test_an_unparseable_reply_raises_a_typed_error():
    with pytest.raises(StructuredOutputError):
        await _parse("I could not produce slides for this content.")


async def test_a_parse_failure_does_not_print_the_model_reply(monkeypatch, capsys):
    """The reply summarises the user's source document; keep it out of stdout.

    Asserted through the node rather than the helper: the leak was the node's
    own ``print(f"Raw response: {content}")``, so calling the helper directly
    would pass either way and prove nothing.
    """
    secret = "CONFIDENTIAL-PATIENT-RECORD-42"

    async def _fake_llm(*_args, **_kwargs):
        return _CannedLLM(f"I cannot do that. Source was: {secret}")

    monkeypatch.setattr(nodes, "get_agent_llm", _fake_llm)

    from app.agents.video_presentation.state import State

    state = State(db_session=None, source_content=secret)
    with pytest.raises(StructuredOutputError):
        await nodes.create_presentation_slides(
            state, {"configurable": {"workspace_id": 1, "video_title": "t"}}
        )

    assert secret not in capsys.readouterr().out


async def test_the_slide_node_uses_the_shared_parser(monkeypatch):
    """The node must not grow a second parsing path alongside the shared one."""
    calls = []

    async def _fake_invoke_json(_llm, _messages, model):
        calls.append(model)
        return PresentationSlides.model_validate_json(_SLIDES_JSON)

    async def _fake_llm(*_args, **_kwargs):
        return _CannedLLM(_SLIDES_JSON)

    monkeypatch.setattr(nodes, "invoke_json", _fake_invoke_json)
    monkeypatch.setattr(nodes, "get_agent_llm", _fake_llm)

    from app.agents.video_presentation.state import State

    state = State(db_session=None, source_content="anything")
    result = await nodes.create_presentation_slides(
        state, {"configurable": {"workspace_id": 1, "video_title": "t"}}
    )

    assert calls == [PresentationSlides]
    assert len(result["slides"]) == 1
