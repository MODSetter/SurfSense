from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.agents.chat.multi_agent_chat.main_agent.middleware.checkpointed_subagent_middleware.resume_routing import (
    collect_pending_tool_calls,
)
from app.agents.chat.multi_agent_chat.subagents.shared.hitl.questions import (
    STRUCTURED_QUESTION_RESPONSE_ADAPTER,
    StructuredQuestion,
    StructuredQuestionInterrupt,
    StructuredQuestionOption,
    StructuredQuestionOrigin,
    validate_structured_response,
)
from app.services.streaming.events.interrupt import normalize_interrupt_payload


def _prompt() -> StructuredQuestionInterrupt:
    return StructuredQuestionInterrupt(
        title="Choose a style",
        origin=StructuredQuestionOrigin(
            kind="preset",
            preset_id="infographic.visual-style",
            preset_version=1,
        ),
        questions=(
            StructuredQuestion(
                id="visual-style",
                prompt="Which visual style should be used?",
                input_type="single_select",
                presentation="visual_cards",
                options=(
                    StructuredQuestionOption(id="auto", label="Auto"),
                    StructuredQuestionOption(id="kawaii", label="Kawaii"),
                ),
            ),
        ),
    )


def test_structured_interrupt_is_preserved_by_sse_normalization() -> None:
    payload = _prompt().model_dump(mode="json")

    assert normalize_interrupt_payload(payload) == payload
    assert "action_requests" not in normalize_interrupt_payload(payload)


def test_structured_interrupt_routes_as_one_subagent_response() -> None:
    value = {**_prompt().model_dump(mode="json"), "tool_call_id": "tc-style"}
    state = SimpleNamespace(
        interrupts=(SimpleNamespace(id="i-style", value=value),)
    )

    assert collect_pending_tool_calls(state) == [("tc-style", 1)]


def test_exact_response_is_accepted() -> None:
    response = STRUCTURED_QUESTION_RESPONSE_ADAPTER.validate_python(
        {
            "type": "respond",
            "preset_id": "infographic.visual-style",
            "preset_version": 1,
            "answers": [
                {"question_id": "visual-style", "option_ids": ["kawaii"]}
            ],
        }
    )

    validate_structured_response(_prompt(), response)


@pytest.mark.parametrize(
    "response",
    [
        {
            "type": "respond",
            "preset_id": "infographic.visual-style",
            "preset_version": 2,
            "answers": [{"question_id": "visual-style", "option_ids": ["kawaii"]}],
        },
        {
            "type": "respond",
            "preset_id": "infographic.visual-style",
            "preset_version": 1,
            "answers": [{"question_id": "unknown", "option_ids": ["kawaii"]}],
        },
        {
            "type": "respond",
            "preset_id": "infographic.visual-style",
            "preset_version": 1,
            "answers": [{"question_id": "visual-style", "option_ids": ["unknown"]}],
        },
    ],
)
def test_stale_or_unknown_responses_fail_closed(response: dict) -> None:
    parsed = STRUCTURED_QUESTION_RESPONSE_ADAPTER.validate_python(response)

    with pytest.raises(ValueError):
        validate_structured_response(_prompt(), parsed)


def test_duplicate_option_ids_are_rejected_at_wire_boundary() -> None:
    with pytest.raises(ValidationError):
        STRUCTURED_QUESTION_RESPONSE_ADAPTER.validate_python(
            {
                "type": "respond",
                "preset_id": "infographic.visual-style",
                "preset_version": 1,
                "answers": [
                    {
                        "question_id": "visual-style",
                        "option_ids": ["kawaii", "kawaii"],
                    }
                ],
            }
        )
