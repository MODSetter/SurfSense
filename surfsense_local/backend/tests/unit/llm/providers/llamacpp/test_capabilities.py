"""What a model can accept, and what its chat template can express.

Two different questions from two different endpoints, and only one of them is a
capability a person should ever see.
"""

import pytest

from modules.llm.providers.llamacpp import Capabilities, Modality, read_capabilities

pytestmark = pytest.mark.unit


def caps(**overrides) -> Capabilities:
    """A text only model whose template supports everything."""
    models = {
        "data": [
            {
                "id": "m",
                "architecture": {"input_modalities": overrides.pop("inputs", ["text"])},
            }
        ]
    }
    props = {
        "chat_template_caps": {
            "supports_system_role": overrides.pop("system_role", True),
            "supports_typed_content": overrides.pop("typed_content", True),
            "supports_tools": overrides.pop("tools", False),
        },
        "default_generation_settings": {"n_ctx": overrides.pop("n_ctx", 16384)},
    }
    return read_capabilities("m", models, props)


def test_a_text_model_reports_no_vision() -> None:
    """A model declaring only text input cannot be sent a picture."""
    assert caps().inputs == (Modality.TEXT,)
    assert not caps().can_see


def test_vision_needs_the_model_and_the_template_to_agree() -> None:
    """A model can accept images architecturally while its template takes only
    string content, leaving no way to hand it one. Checking `input_modalities`
    alone puts a vision badge on a model that cannot be sent a picture.
    """
    both = caps(inputs=["text", "image"], typed_content=True)
    architecture_only = caps(inputs=["text", "image"], typed_content=False)

    assert both.can_see
    assert not architecture_only.can_see


def test_a_template_without_a_system_role_is_recorded() -> None:
    """A live bug this fixes: `build_messages()` always emits a system message
    and it is silently dropped on templates that cannot carry one, taking the
    grounding and the citation instructions with it.
    """
    assert not caps(system_role=False).system_role


def test_the_loaded_window_is_reported_so_the_history_budget_can_respect_it() -> None:
    """Context is fixed at load, so this is the real ceiling for a turn."""
    assert caps(n_ctx=8192).context_tokens == 8192


def test_a_runtime_that_says_nothing_is_assumed_capable_of_the_basics() -> None:
    """An older build reporting no template caps must not lose the system
    message, which is the one field whose absence silently degrades an answer.
    """
    permissive = read_capabilities("m", {"data": [{"id": "m"}]}, {})

    assert permissive.system_role
    assert permissive.inputs == (Modality.TEXT,)
    assert not permissive.can_see


def test_only_the_user_facing_capability_is_named_as_one() -> None:
    """`system_role` and `typed_content` are constraints on how a request is
    built. Neither is meaningful to a person, so neither is a badge."""
    assert caps(inputs=["text", "image"]).user_facing == ("vision",)
    assert caps().user_facing == ()
