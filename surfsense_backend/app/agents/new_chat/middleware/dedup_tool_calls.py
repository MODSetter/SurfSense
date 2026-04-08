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

_HITL_TOOL_DEDUP_KEYS: dict[str, str] = {
    "delete_calendar_event": "event_title_or_id",
    "update_calendar_event": "event_title_or_id",
    "trash_gmail_email": "email_subject_or_id",
    "update_gmail_draft": "draft_subject_or_id",
    "delete_google_drive_file": "file_name",
    "delete_onedrive_file": "file_name",
    "delete_notion_page": "page_title",
    "update_notion_page": "page_title",
    "delete_linear_issue": "issue_ref",
    "update_linear_issue": "issue_ref",
    "update_jira_issue": "issue_title_or_key",
    "delete_jira_issue": "issue_title_or_key",
    "update_confluence_page": "page_title_or_id",
    "delete_confluence_page": "page_title_or_id",
}


class DedupHITLToolCallsMiddleware(AgentMiddleware):  # type: ignore[type-arg]
    """Remove duplicate HITL tool calls from a single LLM response.

    Only the **first** occurrence of each (tool-name, primary-arg-value)
    pair is kept; subsequent duplicates are silently dropped.
    """

    tools = ()

    def after_model(
        self, state: AgentState, runtime: Runtime[Any]
    ) -> dict[str, Any] | None:
        return self._dedup(state)

    async def aafter_model(
        self, state: AgentState, runtime: Runtime[Any]
    ) -> dict[str, Any] | None:
        return self._dedup(state)

    @staticmethod
    def _dedup(state: AgentState) -> dict[str, Any] | None:  # type: ignore[type-arg]
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
            dedup_key_arg = _HITL_TOOL_DEDUP_KEYS.get(name)
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
