"""Tests for the default auto-approval list in ``hitl.request_approval``.

These pin the policy that low-stakes connector creation tools (drafts,
new-file creates) skip the HITL interrupt by default. Without this set,
every "draft my newsletter" turn used to fire ~3 interrupts before any
useful work happened.
"""

from __future__ import annotations

import pytest

from app.agents.new_chat.tools.hitl import (
    DEFAULT_AUTO_APPROVED_TOOLS,
    HITLResult,
    request_approval,
)

pytestmark = pytest.mark.unit


class TestDefaultAutoApprovedToolsList:
    def test_set_contains_expected_creation_tools(self) -> None:
        # If anyone changes the policy list, we want a single test to
        # update so the contract is explicit. Keep this in sync with
        # ``hitl.DEFAULT_AUTO_APPROVED_TOOLS``.
        expected = {
            "create_gmail_draft",
            "update_gmail_draft",
            "create_calendar_event",
            "create_notion_page",
            "create_confluence_page",
            "create_google_drive_file",
            "create_dropbox_file",
            "create_onedrive_file",
        }
        assert expected == DEFAULT_AUTO_APPROVED_TOOLS

    def test_set_is_immutable(self) -> None:
        # frozenset prevents accidental at-runtime mutation that would
        # silently widen the auto-approval surface.
        assert isinstance(DEFAULT_AUTO_APPROVED_TOOLS, frozenset)

    def test_send_tools_are_not_auto_approved(self) -> None:
        # External-broadcast / destructive tools must always prompt.
        for tool_name in (
            "send_gmail_email",
            "send_discord_message",
            "send_teams_message",
            "delete_notion_page",
            "delete_calendar_event",
        ):
            assert tool_name not in DEFAULT_AUTO_APPROVED_TOOLS, (
                f"{tool_name} must remain HITL-gated"
            )


class TestRequestApprovalAutoBypass:
    def test_auto_approved_tool_skips_interrupt(self) -> None:
        # No interrupt mock set up — if the function attempted to call
        # ``langgraph.types.interrupt`` it would raise GraphInterrupt.
        # The fact that we get a clean HITLResult proves the bypass.
        result = request_approval(
            action_type="gmail_draft_creation",
            tool_name="create_gmail_draft",
            params={"to": "alice@example.com", "subject": "hi", "body": "hey"},
        )
        assert isinstance(result, HITLResult)
        assert result.rejected is False
        assert result.decision_type == "auto_approved"
        # Original params are preserved untouched (no user edits possible).
        assert result.params == {
            "to": "alice@example.com",
            "subject": "hi",
            "body": "hey",
        }

    def test_non_listed_tool_still_attempts_interrupt(self) -> None:
        # A tool NOT in the default list must reach ``langgraph.interrupt``.
        # Outside a runnable context that call raises a RuntimeError —
        # which is exactly the signal we want: the bypass did NOT fire.
        with pytest.raises(RuntimeError, match="runnable context"):
            request_approval(
                action_type="gmail_email_send",
                tool_name="send_gmail_email",
                params={"to": "alice@example.com", "subject": "hi", "body": "hey"},
            )

    def test_user_trusted_tools_still_take_precedence(self) -> None:
        # ``trusted_tools`` (per-connector "always allow" from MCP/UI)
        # was checked BEFORE the default list and must keep working
        # for tools outside the default list.
        result = request_approval(
            action_type="mcp_tool_call",
            tool_name="my_custom_mcp_tool",
            params={"x": 1},
            trusted_tools=["my_custom_mcp_tool"],
        )
        assert result.decision_type == "trusted"
        assert result.rejected is False

    def test_auto_approved_overrides_no_trusted_tools(self) -> None:
        # When trusted_tools is empty and tool is in the default list,
        # we should still bypass — proves the order in request_approval.
        result = request_approval(
            action_type="notion_page_creation",
            tool_name="create_notion_page",
            params={"title": "Plan"},
            trusted_tools=[],
        )
        assert result.decision_type == "auto_approved"
