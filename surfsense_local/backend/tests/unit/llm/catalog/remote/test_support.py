"""Support reads the manifest straight through; None stays None."""

import pytest

from modules.llm.catalog.remote.manifest.schema import RemoteModel
from modules.llm.catalog.remote.support import supports

pytestmark = pytest.mark.unit


def _entry(**fields: object) -> RemoteModel:
    base: dict[str, object] = {
        "name": "model",
        "family": None,
        "description": None,
        "release_date": None,
        "status": None,
        "modalities": {"input": ["text"], "output": ["text"]},
        "context": None,
        "output_limit": None,
        "tool_call": None,
        "reasoning": None,
        "reasoning_options": None,
        "structured_output": None,
        "temperature": None,
        "call": None,
    }
    return RemoteModel.model_validate({**base, **fields})


def test_tool_call_and_reasoning_are_read_straight_through() -> None:
    """Both are filled in on every entry models.dev carries."""
    claude = _entry(tool_call=True, reasoning=True, structured_output=True)

    assert (supports(claude).tool_call, supports(claude).reasoning) == (True, True)


def test_an_unrecorded_structured_output_is_not_a_no() -> None:
    """models.dev omits the field on 1,954 tool-calling models, Mistral's among
    them, and says `false` explicitly on 739 others. Reading absent as no would
    route models that do support JSON schema to the weaker agent system."""
    codestral = _entry(tool_call=True, reasoning=False)

    assert supports(codestral).structured_output is None


def test_a_declared_no_to_structured_output_is_kept() -> None:
    """The distinction absence would destroy."""
    entry = _entry(tool_call=True, reasoning=True, structured_output=False)

    assert supports(entry).structured_output is False


def test_the_context_window_is_the_manifest_context() -> None:
    """What an agent budgets its prompt against."""
    assert supports(_entry(context=400000)).context_window == 400000
