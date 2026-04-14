"""Middleware that deduplicates HITL tool calls within a single LLM response.

When the LLM emits multiple calls to the same HITL tool with the same
primary argument (e.g. two ``delete_calendar_event("Doctor Appointment")``),
only the first call is kept.  Non-HITL tools are never touched.

This runs in the ``after_model`` hook — **before** any tool executes — so
the duplicate call is stripped from the AIMessage that gets checkpointed.
That means it is also safe across LangGraph ``interrupt()`` boundaries:
the removed call will never appear on graph resume.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain.agents.middleware import AgentMiddleware, AgentState
from langgraph.runtime import Runtime

logger = logging.getLogger(__name__)

_NATIVE_HITL_TOOL_DEDUP_KEYS: dict[str, str] = {
    # Gmail
    "send_gmail_email": "subject",
    "create_gmail_draft": "subject",
    "update_gmail_draft": "draft_subject_or_id",
    "trash_gmail_email": "email_subject_or_id",
    # Google Calendar
    "create_calendar_event": "title",
    "update_calendar_event": "event_title_or_id",
    "delete_calendar_event": "event_title_or_id",
    # Google Drive
    "create_google_drive_file": "file_name",
    "delete_google_drive_file": "file_name",
    # OneDrive
    "create_onedrive_file": "file_name",
    "delete_onedrive_file": "file_name",
    # Dropbox
    "create_dropbox_file": "file_name",
    "delete_dropbox_file": "file_name",
    # Notion
    "create_notion_page": "title",
    "update_notion_page": "page_title",
    "delete_notion_page": "page_title",
    # Linear
    "create_linear_issue": "title",
    "update_linear_issue": "issue_ref",
    "delete_linear_issue": "issue_ref",
    # Jira
    "create_jira_issue": "summary",
    "update_jira_issue": "issue_title_or_key",
    "delete_jira_issue": "issue_title_or_key",
    # Confluence
    "create_confluence_page": "title",
    "update_confluence_page": "page_title_or_id",
    "delete_confluence_page": "page_title_or_id",
}


class DedupHITLToolCallsMiddleware(AgentMiddleware):  # type: ignore[type-arg]
    """Remove duplicate HITL tool calls from a single LLM response.

    Only the **first** occurrence of each (tool-name, primary-arg-value)
    pair is kept; subsequent duplicates are silently dropped.

    The dedup map is built from two sources:

    1. A comprehensive list of native HITL tools (hardcoded above).
    2. Any ``StructuredTool`` instances passed via *agent_tools* whose
       ``metadata`` contains ``{"hitl": True, "hitl_dedup_key": "..."}``.
       This is how MCP tools automatically get dedup support.
    """

    tools = ()

    def __init__(self, *, agent_tools: list[Any] | None = None) -> None:
        self._dedup_keys: dict[str, str] = dict(_NATIVE_HITL_TOOL_DEDUP_KEYS)
        for t in agent_tools or []:
            meta = getattr(t, "metadata", None) or {}
            if meta.get("hitl") and meta.get("hitl_dedup_key"):
                self._dedup_keys[t.name] = meta["hitl_dedup_key"]

    def after_model(
        self, state: AgentState, runtime: Runtime[Any]
    ) -> dict[str, Any] | None:
        return self._dedup(state, self._dedup_keys)

    async def aafter_model(
        self, state: AgentState, runtime: Runtime[Any]
    ) -> dict[str, Any] | None:
        return self._dedup(state, self._dedup_keys)

    @staticmethod
    def _dedup(
        state: AgentState, dedup_keys: dict[str, str]  # type: ignore[type-arg]
    ) -> dict[str, Any] | None:
        messages = state.get("messages")
        if not messages:
            return None

        last_msg = messages[-1]
        if last_msg.type != "ai" or not getattr(last_msg, "tool_calls", None):
            return None

        tool_calls: list[dict[str, Any]] = last_msg.tool_calls
        seen: set[tuple[str, str]] = set()
        deduped: list[dict[str, Any]] = []

        for tc in tool_calls:
            name = tc.get("name", "")
            dedup_key_arg = dedup_keys.get(name)
            if dedup_key_arg is not None:
                arg_val = str(tc.get("args", {}).get(dedup_key_arg, "")).lower()
                key = (name, arg_val)
                if key in seen:
                    logger.info(
                        "Dedup: dropped duplicate HITL tool call %s(%s)",
                        name,
                        arg_val,
                    )
                    continue
                seen.add(key)
            deduped.append(tc)

        if len(deduped) == len(tool_calls):
            return None

        updated_msg = last_msg.model_copy(update={"tool_calls": deduped})
        return {"messages": [updated_msg]}
