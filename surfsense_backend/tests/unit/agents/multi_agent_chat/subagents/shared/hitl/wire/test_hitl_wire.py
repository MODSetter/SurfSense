"""Unit contract for the unified LC HITL wire format.

Both the self-gated approval primitive (``request_approval``) and the
middleware-gated permission ask (``PermissionMiddleware``) must serialize
to the same wire shape so the parallel-HITL routing layer
(``collect_pending_tool_calls`` + ``slice_decisions_by_tool_call`` +
``build_lg_resume_map``) sees one format.

These tests pin the shape:

- Builder always emits ``action_requests`` (1 entry) + ``review_configs``
  + ``interrupt_type``; ``context`` rides through verbatim when present.
- Parser tolerates the standard LC envelope, bare scalar strings, and
  unrecognized shapes (failing closed to ``reject``).
- Edited args round-trip through both nested (``edited_action.args``) and
  flat (``args``) shapes without inventing values for the empty case.
"""

from __future__ import annotations

from app.agents.multi_agent_chat.subagents.shared.hitl.wire import (
    LC_DECISION_APPROVE,
    LC_DECISION_EDIT,
    LC_DECISION_REJECT,
    SURFSENSE_DECISION_APPROVE_ALWAYS,
    build_lc_hitl_payload,
    parse_lc_envelope,
)


class TestBuildLcHitlPayload:
    def test_minimal_payload_has_one_action_request_and_one_review_config(self):
        payload = build_lc_hitl_payload(
            tool_name="send_email",
            args={"to": "x@y.z"},
            allowed_decisions=[LC_DECISION_APPROVE, LC_DECISION_REJECT],
            interrupt_type="gmail_email_send",
        )
        assert payload["action_requests"] == [
            {"name": "send_email", "args": {"to": "x@y.z"}}
        ]
        assert payload["review_configs"] == [
            {
                "action_name": "send_email",
                "allowed_decisions": [LC_DECISION_APPROVE, LC_DECISION_REJECT],
            }
        ]
        assert payload["interrupt_type"] == "gmail_email_send"
        assert "context" not in payload, "context must be omitted when not provided"

    def test_none_args_normalized_to_empty_dict(self):
        """FE expects a stable shape; ``None`` would crash card rendering."""
        payload = build_lc_hitl_payload(
            tool_name="ping",
            args=None,  # type: ignore[arg-type]
            allowed_decisions=[LC_DECISION_APPROVE],
            interrupt_type="self_gated",
        )
        assert payload["action_requests"][0]["args"] == {}

    def test_description_attached_only_when_provided(self):
        with_desc = build_lc_hitl_payload(
            tool_name="t",
            args={},
            allowed_decisions=[LC_DECISION_APPROVE],
            interrupt_type="x",
            description="please review",
        )
        without = build_lc_hitl_payload(
            tool_name="t",
            args={},
            allowed_decisions=[LC_DECISION_APPROVE],
            interrupt_type="x",
        )
        assert with_desc["action_requests"][0]["description"] == "please review"
        assert "description" not in without["action_requests"][0]

    def test_context_passed_through_verbatim(self):
        ctx = {"patterns": ["rm/*"], "rules": [], "always": ["rm/*"]}
        payload = build_lc_hitl_payload(
            tool_name="rm",
            args={"path": "/tmp"},
            allowed_decisions=[
                LC_DECISION_APPROVE,
                LC_DECISION_REJECT,
                SURFSENSE_DECISION_APPROVE_ALWAYS,
            ],
            interrupt_type="permission_ask",
            context=ctx,
        )
        assert payload["context"] == ctx

    def test_allowed_decisions_list_is_copied_not_aliased(self):
        """A caller mutating their original list must not corrupt the payload."""
        decisions = [LC_DECISION_APPROVE]
        payload = build_lc_hitl_payload(
            tool_name="t",
            args={},
            allowed_decisions=decisions,
            interrupt_type="x",
        )
        decisions.append(LC_DECISION_REJECT)
        assert payload["review_configs"][0]["allowed_decisions"] == [
            LC_DECISION_APPROVE
        ]


class TestParseLcEnvelope:
    def test_standard_lc_envelope_returns_typed_decision(self):
        parsed = parse_lc_envelope({"decisions": [{"type": "approve"}]})
        assert parsed.decision_type == "approve"
        assert parsed.edited_args is None
        assert parsed.message is None

    def test_bare_scalar_string_passes_through_lowercased(self):
        assert parse_lc_envelope("APPROVE_ALWAYS").decision_type == "approve_always"
        assert parse_lc_envelope("once").decision_type == "once"

    def test_non_dict_non_string_collapses_to_reject(self):
        """Failing closed: ambiguous input must never proceed."""
        assert parse_lc_envelope(42).decision_type == "reject"
        assert parse_lc_envelope(None).decision_type == "reject"
        assert parse_lc_envelope(["bogus"]).decision_type == "reject"

    def test_missing_decision_type_collapses_to_reject(self):
        assert parse_lc_envelope({"decisions": [{}]}).decision_type == "reject"
        assert parse_lc_envelope({"foo": "bar"}).decision_type == "reject"

    def test_edit_extracts_nested_args(self):
        parsed = parse_lc_envelope(
            {
                "decisions": [
                    {
                        "type": LC_DECISION_EDIT,
                        "edited_action": {"args": {"to": "edited@y.z"}},
                    }
                ]
            }
        )
        assert parsed.decision_type == "edit"
        assert parsed.edited_args == {"to": "edited@y.z"}

    def test_edit_falls_back_to_flat_args(self):
        parsed = parse_lc_envelope(
            {"decisions": [{"type": "edit", "args": {"k": "v"}}]}
        )
        assert parsed.edited_args == {"k": "v"}

    def test_edit_with_empty_args_yields_none_edited(self):
        """Empty edited_args means "no edits" — caller treats as plain approve."""
        parsed = parse_lc_envelope(
            {"decisions": [{"type": "edit", "edited_action": {"args": {}}}]}
        )
        assert parsed.edited_args is None

    def test_message_picked_from_either_feedback_or_message_field(self):
        with_feedback = parse_lc_envelope(
            {"decisions": [{"type": "reject", "feedback": "no thanks"}]}
        )
        with_message = parse_lc_envelope(
            {"decisions": [{"type": "reject", "message": "no thanks"}]}
        )
        assert with_feedback.message == "no thanks"
        assert with_message.message == "no thanks"

    def test_blank_message_treated_as_absent(self):
        parsed = parse_lc_envelope(
            {"decisions": [{"type": "reject", "message": "   "}]}
        )
        assert parsed.message is None
