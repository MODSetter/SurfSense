"""Pin the wire compactness rule and the top-level ``emitted_by`` field name."""

from __future__ import annotations

import pytest

from app.services.streaming.emitter import (
    Emitter,
    attach_emitted_by,
    main_emitter,
    subagent_emitter,
)

pytestmark = pytest.mark.unit


def test_main_emitter_payload_contains_only_level() -> None:
    payload = main_emitter().to_payload()
    assert payload == {"level": "main"}


def test_subagent_emitter_payload_includes_all_set_fields() -> None:
    payload = subagent_emitter(
        subagent_type="deliverables",
        subagent_run_id="subagent_abc",
        parent_tool_call_id="call_xyz",
    ).to_payload()
    assert payload == {
        "level": "subagent",
        "subagent_type": "deliverables",
        "subagent_run_id": "subagent_abc",
        "parent_tool_call_id": "call_xyz",
    }


def test_subagent_emitter_payload_omits_unset_optional_fields() -> None:
    """parent_tool_call_id is None when the run is started outside a tool boundary."""
    payload = Emitter(
        level="subagent",
        subagent_type="email",
        subagent_run_id="subagent_1",
    ).to_payload()
    assert "parent_tool_call_id" not in payload
    assert payload["subagent_type"] == "email"


def test_extra_fields_merge_into_payload() -> None:
    """Future extension fields (e.g. lane colour, label) flow through ``extra``."""
    emitter = subagent_emitter(
        subagent_type="search",
        subagent_run_id="r1",
        extra={"label": "Web Search"},
    )
    assert emitter.to_payload()["label"] == "Web Search"


def test_attach_emitted_by_with_none_is_noop() -> None:
    payload = {"type": "text-delta", "delta": "hi"}
    result = attach_emitted_by(payload, None)
    assert "emitted_by" not in result
    assert result is payload


def test_attach_emitted_by_adds_payload_under_snake_case_top_level_key() -> None:
    payload = {"type": "text-delta", "delta": "hi"}
    attach_emitted_by(
        payload,
        subagent_emitter(
            subagent_type="x",
            subagent_run_id="y",
            parent_tool_call_id="z",
        ),
    )
    assert payload["emitted_by"] == {
        "level": "subagent",
        "subagent_type": "x",
        "subagent_run_id": "y",
        "parent_tool_call_id": "z",
    }
