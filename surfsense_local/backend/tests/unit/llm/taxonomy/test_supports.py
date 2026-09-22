"""Fixtures are real models.dev entries; counts were measured over all 223 providers."""

import pytest

from modules.llm.taxonomy import supports

pytestmark = pytest.mark.unit


def test_tool_call_and_reasoning_are_read_straight_through() -> None:
    """Both are filled in on all 8,077 entries, so neither needs a default."""
    claude = {"tool_call": True, "reasoning": True, "structured_output": True}

    assert (supports(claude).tool_call, supports(claude).reasoning) == (True, True)


def test_an_unrecorded_structured_output_is_not_a_no() -> None:
    """models.dev omits the field on 1,954 tool-calling models, Mistral's among
    them, and says `false` explicitly on 739 others. Reading absent as no would
    route models that do support JSON schema to the weaker agent system."""
    codestral = {"tool_call": True, "reasoning": False}

    assert supports(codestral).structured_output is None


def test_a_declared_no_to_structured_output_is_kept() -> None:
    """The distinction absence would destroy."""
    entry = {"tool_call": True, "reasoning": True, "structured_output": False}

    assert supports(entry).structured_output is False


def test_the_context_window_is_read_from_the_limit() -> None:
    """What an agent budgets its prompt against."""
    gpt_5 = {"limit": {"context": 400000, "input": 272000, "output": 128000}}

    assert supports(gpt_5).context_window == 400000


def test_a_zero_context_window_is_not_a_window_of_zero() -> None:
    """136 entries say 0, all of them image or video models where a token
    window means nothing. Passing that to a budget would floor every prompt."""
    image_model = {"limit": {"context": 0, "output": 0}}

    assert supports(image_model).context_window is None
    assert supports({}).context_window is None
