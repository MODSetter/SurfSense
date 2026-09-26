"""Templates that cannot carry a system message.

`build_messages()` always emits one. On a template with no system role it is
dropped, and it is carrying the grounding and the citation instructions, so the
model answers from nothing and nothing says why.
"""

import pytest

from modules.llm.providers.llamacpp import Capabilities, Modality
from modules.llm.providers.llamacpp.messages import for_template
from modules.llm.providers.types import Message

pytestmark = pytest.mark.unit

GROUNDING = "Answer from the sources. Cite with [n]."
TURNS = [
    Message("system", GROUNDING),
    Message("user", "what did the report say?"),
]


def caps(system_role: bool) -> Capabilities:
    """A text only model whose template may or may not carry a system role."""
    return Capabilities(
        inputs=(Modality.TEXT,),
        system_role=system_role,
        typed_content=False,
        tools=False,
        context_tokens=16384,
    )


def test_a_template_with_a_system_role_is_left_alone() -> None:
    """The common case, so the fold cannot fire where it is not needed."""
    assert for_template(TURNS, caps(system_role=True)) == TURNS


def test_a_template_without_one_keeps_the_instructions_in_the_first_user_turn() -> None:
    """Folded in, not dropped. The alternative is an ungrounded answer that
    looks confident and cites nothing."""
    adjusted = for_template(TURNS, caps(system_role=False))

    assert [m.role for m in adjusted] == ["user"]
    assert GROUNDING in adjusted[0].content
    assert "what did the report say?" in adjusted[0].content


def test_folding_preserves_the_order_the_model_reads_in() -> None:
    """Instructions before the question, as the system message was."""
    folded = for_template(TURNS, caps(system_role=False))[0].content

    assert folded.index(GROUNDING) < folded.index("what did the report say?")


def test_a_conversation_with_no_system_message_is_untouched() -> None:
    """Nothing to fold, so nothing is rewritten."""
    turns = [Message("user", "hello")]

    assert for_template(turns, caps(system_role=False)) == turns


def test_history_after_the_system_message_survives_the_fold() -> None:
    """Only the system message moves; the conversation is not rewritten."""
    turns = [
        Message("system", GROUNDING),
        Message("user", "first"),
        Message("assistant", "reply"),
        Message("user", "second"),
    ]

    adjusted = for_template(turns, caps(system_role=False))

    assert [m.role for m in adjusted] == ["user", "assistant", "user"]
    assert adjusted[-1].content == "second"
