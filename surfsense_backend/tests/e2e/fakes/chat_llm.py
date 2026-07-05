from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any, Self

from langchain_core.callbacks import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult

DRIVE_CANARY_TOKEN = "SURFSENSE_E2E_CANARY_TOKEN_DRIVE_001"
DRIVE_PDF_CANARY_TOKEN = "SURFSENSE_E2E_CANARY_TOKEN_DRIVE_PDF_001"
DRIVE_PDF_CANARY_FILE = "e2e-canary.pdf"
COMPOSIO_DRIVE_PDF_CANARY_TOKEN = "SURFSENSE_E2E_CANARY_TOKEN_COMPOSIO_DRIVE_PDF_001"
COMPOSIO_DRIVE_PDF_CANARY_FILE = "e2e-composio-canary.pdf"
GMAIL_CANARY_TOKEN = "SURFSENSE_E2E_CANARY_TOKEN_GMAIL_001"
GMAIL_CANARY_SUBJECT = "E2E Canary Email"
GMAIL_CANARY_MESSAGE_ID = "fake-msg-canary-001"
CALENDAR_CANARY_TOKEN = "SURFSENSE_E2E_CANARY_TOKEN_CALENDAR_001"
CALENDAR_CANARY_SUMMARY = "E2E Canary Calendar Event"
ONEDRIVE_CANARY_TOKEN = "SURFSENSE_E2E_CANARY_TOKEN_ONEDRIVE_001"
ONEDRIVE_CANARY_FILE = "e2e-onedrive-canary.txt"
ONEDRIVE_PDF_CANARY_TOKEN = "SURFSENSE_E2E_CANARY_TOKEN_ONEDRIVE_PDF_001"
ONEDRIVE_PDF_CANARY_FILE = "e2e-onedrive-canary.pdf"
DROPBOX_CANARY_TOKEN = "SURFSENSE_E2E_CANARY_TOKEN_DROPBOX_001"
DROPBOX_CANARY_FILE = "e2e-dropbox-canary.txt"
DROPBOX_PDF_CANARY_TOKEN = "SURFSENSE_E2E_CANARY_TOKEN_DROPBOX_PDF_001"
DROPBOX_PDF_CANARY_FILE = "e2e-dropbox-canary.pdf"
NOTION_CANARY_TOKEN = "SURFSENSE_E2E_CANARY_TOKEN_NOTION_001"
NOTION_CANARY_TITLE = "E2E Canary Notion Page"
CONFLUENCE_CANARY_TOKEN = "SURFSENSE_E2E_CANARY_TOKEN_CONFLUENCE_001"
CONFLUENCE_CANARY_TITLE = "E2E Canary Confluence Page"
LINEAR_CANARY_TOKEN = "SURFSENSE_E2E_CANARY_TOKEN_LINEAR_001"
LINEAR_CANARY_TITLE = "E2E Canary Linear Issue"
JIRA_CANARY_TOKEN = "SURFSENSE_E2E_CANARY_TOKEN_JIRA_001"
JIRA_CANARY_SUMMARY = "E2E Canary Jira Issue"
JIRA_CANARY_KEY = "E2E-101"
SLACK_CANARY_TOKEN = "SURFSENSE_E2E_CANARY_TOKEN_SLACK_001"
SLACK_CANARY_CHANNEL = "slack-e2e-canary"
CLICKUP_CANARY_TOKEN = "SURFSENSE_E2E_CANARY_TOKEN_CLICKUP_001"
CLICKUP_CANARY_TITLE = "E2E Canary ClickUp Task"
CLICKUP_CANARY_TASK_ID = "fake-clickup-task-canary-001"
MANUAL_UPLOAD_MD_CANARY_TOKEN = "E2E-MANUAL-UPLOAD-MD-CANARY-7f3a"
MANUAL_UPLOAD_MD_CANARY_FILE = "canary.md"
MANUAL_UPLOAD_PDF_CANARY_TOKEN = "E2E-MANUAL-UPLOAD-PDF-CANARY-9d2b"
MANUAL_UPLOAD_PDF_CANARY_FILE = "canary.pdf"
NO_RELEVANT_CONTENT_SENTINEL = "No relevant indexed content found."
NO_RELEVANT_CONTENT_QUERY = "E2E_NO_RELEVANT_CONTENT_SMOKE"


def _content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(_content_to_text(item) for item in content)
    if isinstance(content, dict):
        text = content.get("text") or content.get("content")
        if isinstance(text, str):
            return text
        return json.dumps(content, sort_keys=True)
    if content is None:
        return ""
    return str(content)


def _messages_to_text(messages: list[BaseMessage]) -> str:
    return "\n".join(_content_to_text(message.content) for message in messages)


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(needle.lower() in lowered for needle in needles)


def _latest_tool_message(messages: list[BaseMessage]) -> BaseMessage | None:
    return next(
        (message for message in reversed(messages) if message.type == "tool"), None
    )


class FakeChatLLM(BaseChatModel):
    @property
    def _llm_type(self) -> str:
        return "e2e-fake-chat"

    def bind_tools(self, tools: Any, **kwargs: Any) -> Self:
        return self

    def _response_for(self, messages: list[BaseMessage]) -> str:
        latest_human = next(
            (
                _content_to_text(message.content)
                for message in reversed(messages)
                if message.type == "human"
            ),
            "",
        )
        if NO_RELEVANT_CONTENT_QUERY in latest_human:
            return NO_RELEVANT_CONTENT_SENTINEL

        prompt_text = _messages_to_text(messages)
        latest_tool = _latest_tool_message(messages)
        latest_tool_name = getattr(latest_tool, "name", None)
        latest_tool_text = _content_to_text(latest_tool.content) if latest_tool else ""

        if (
            latest_tool_name == "read_gmail_email"
            and GMAIL_CANARY_TOKEN in latest_tool_text
        ):
            return f"Gmail live tool content found: {GMAIL_CANARY_TOKEN}"
        if (
            latest_tool_name == "search_gmail"
            and GMAIL_CANARY_MESSAGE_ID in latest_tool_text
        ):
            return "Reading the matching Gmail message next."
        if (
            latest_tool_name == "search_calendar_events"
            and CALENDAR_CANARY_TOKEN in latest_tool_text
        ):
            return f"Calendar live tool content found: {CALENDAR_CANARY_TOKEN}"
        if (
            latest_tool_name == "list_issues"
            and LINEAR_CANARY_TOKEN in latest_tool_text
        ):
            return f"Linear live tool content found: {LINEAR_CANARY_TOKEN}"
        if (
            latest_tool_name == "searchJiraIssuesUsingJql"
            and JIRA_CANARY_TOKEN in latest_tool_text
        ):
            return f"Jira live tool content found: {JIRA_CANARY_TOKEN}"
        if (
            latest_tool_name == "slack_search_channels"
            and SLACK_CANARY_TOKEN in latest_tool_text
        ):
            return f"Slack live tool content found: {SLACK_CANARY_TOKEN}"
        if (
            latest_tool_name in {"clickup_search", "clickup_get_task"}
            and CLICKUP_CANARY_TOKEN in latest_tool_text
        ):
            return f"ClickUp live tool content found: {CLICKUP_CANARY_TOKEN}"
        if latest_tool_name == "search" and NOTION_CANARY_TOKEN in latest_tool_text:
            return f"Notion live tool content found: {NOTION_CANARY_TOKEN}"
        if (
            latest_tool_name == "searchConfluenceUsingCql"
            and CONFLUENCE_CANARY_TOKEN in latest_tool_text
        ):
            return f"Confluence live tool content found: {CONFLUENCE_CANARY_TOKEN}"

        wants_gmail = _contains_any(
            latest_human,
            ("gmail", "email", "message", GMAIL_CANARY_SUBJECT),
        )
        wants_calendar = _contains_any(
            latest_human,
            ("calendar", "event", "meeting", CALENDAR_CANARY_SUMMARY),
        )
        wants_drive = _contains_any(
            latest_human,
            ("drive", "file", "e2e-canary.txt"),
        )
        wants_drive_pdf = _contains_any(
            latest_human,
            (
                "drive pdf",
                DRIVE_PDF_CANARY_FILE,
                DRIVE_PDF_CANARY_TOKEN,
                COMPOSIO_DRIVE_PDF_CANARY_FILE,
                COMPOSIO_DRIVE_PDF_CANARY_TOKEN,
            ),
        ) or (wants_drive and "pdf" in latest_human.lower())
        wants_onedrive = _contains_any(
            latest_human,
            ("onedrive", ONEDRIVE_CANARY_FILE, ONEDRIVE_CANARY_TOKEN),
        )
        wants_onedrive_pdf = wants_onedrive and _contains_any(
            latest_human,
            ("pdf", ONEDRIVE_PDF_CANARY_FILE, ONEDRIVE_PDF_CANARY_TOKEN),
        )
        wants_dropbox = _contains_any(
            latest_human,
            ("dropbox", DROPBOX_CANARY_FILE, DROPBOX_CANARY_TOKEN),
        )
        wants_dropbox_pdf = wants_dropbox and _contains_any(
            latest_human,
            ("pdf", DROPBOX_PDF_CANARY_FILE, DROPBOX_PDF_CANARY_TOKEN),
        )
        wants_notion = _contains_any(
            latest_human,
            ("notion", "page", NOTION_CANARY_TITLE),
        )
        wants_confluence = _contains_any(
            latest_human,
            ("confluence", CONFLUENCE_CANARY_TITLE),
        )
        wants_linear = _contains_any(
            latest_human,
            ("linear", "issue", LINEAR_CANARY_TITLE),
        )
        wants_jira = _contains_any(
            latest_human,
            (
                "jira",
                "atlassian",
                JIRA_CANARY_SUMMARY,
                JIRA_CANARY_KEY,
                "surfsense-e2e.atlassian.net",
                "fake-jira-cloud-001",
            ),
        )
        wants_slack = _contains_any(
            latest_human,
            ("slack", SLACK_CANARY_TOKEN),
        )
        wants_clickup = _contains_any(
            latest_human,
            ("clickup", CLICKUP_CANARY_TITLE),
        )
        wants_manual_upload = _contains_any(
            latest_human,
            (
                "uploaded",
                "manual upload",
                MANUAL_UPLOAD_MD_CANARY_FILE,
                MANUAL_UPLOAD_PDF_CANARY_FILE,
                MANUAL_UPLOAD_MD_CANARY_TOKEN,
                MANUAL_UPLOAD_PDF_CANARY_TOKEN,
            ),
        )
        wants_manual_upload_pdf = wants_manual_upload and _contains_any(
            latest_human,
            ("pdf", MANUAL_UPLOAD_PDF_CANARY_FILE, MANUAL_UPLOAD_PDF_CANARY_TOKEN),
        )
        wants_manual_upload_md = wants_manual_upload and _contains_any(
            latest_human,
            (
                "markdown",
                ".md",
                MANUAL_UPLOAD_MD_CANARY_FILE,
                MANUAL_UPLOAD_MD_CANARY_TOKEN,
            ),
        )
        has_gmail_evidence = (
            GMAIL_CANARY_SUBJECT in prompt_text
            or GMAIL_CANARY_MESSAGE_ID in prompt_text
            or GMAIL_CANARY_TOKEN in prompt_text
        )
        has_calendar_evidence = (
            CALENDAR_CANARY_SUMMARY in prompt_text
            or CALENDAR_CANARY_TOKEN in prompt_text
        )
        has_drive_evidence = (
            "e2e-canary.txt" in prompt_text
            or "fake-file-canary" in prompt_text
            or DRIVE_CANARY_TOKEN in prompt_text
        )
        has_native_drive_pdf_evidence = (
            DRIVE_PDF_CANARY_FILE in prompt_text
            or "fake-file-pdf-native" in prompt_text
            or DRIVE_PDF_CANARY_TOKEN in prompt_text
        )
        has_composio_drive_pdf_evidence = (
            COMPOSIO_DRIVE_PDF_CANARY_FILE in prompt_text
            or "fake-file-pdf-composio" in prompt_text
            or COMPOSIO_DRIVE_PDF_CANARY_TOKEN in prompt_text
        )
        has_onedrive_evidence = (
            ONEDRIVE_CANARY_FILE in prompt_text
            or "fake-onedrive-canary" in prompt_text
            or ONEDRIVE_CANARY_TOKEN in prompt_text
        )
        has_onedrive_pdf_evidence = (
            ONEDRIVE_PDF_CANARY_FILE in prompt_text
            or "fake-onedrive-pdf-canary" in prompt_text
            or ONEDRIVE_PDF_CANARY_TOKEN in prompt_text
        )
        has_dropbox_evidence = (
            DROPBOX_CANARY_FILE in prompt_text
            or "id:fake-dropbox-canary" in prompt_text
            or DROPBOX_CANARY_TOKEN in prompt_text
        )
        has_dropbox_pdf_evidence = (
            DROPBOX_PDF_CANARY_FILE in prompt_text
            or "id:fake-dropbox-pdf-canary" in prompt_text
            or DROPBOX_PDF_CANARY_TOKEN in prompt_text
        )
        has_notion_evidence = (
            NOTION_CANARY_TITLE in prompt_text or NOTION_CANARY_TOKEN in prompt_text
        )
        has_confluence_evidence = (
            CONFLUENCE_CANARY_TITLE in prompt_text
            or CONFLUENCE_CANARY_TOKEN in prompt_text
            or "fake-confluence-page-canary-001" in prompt_text
            or "fake-confluence-space-001" in prompt_text
        )
        has_linear_evidence = (
            LINEAR_CANARY_TITLE in prompt_text
            or LINEAR_CANARY_TOKEN in prompt_text
            or "fake-linear-issue-canary-001" in prompt_text
        )
        has_jira_evidence = (
            JIRA_CANARY_SUMMARY in prompt_text
            or JIRA_CANARY_TOKEN in prompt_text
            or JIRA_CANARY_KEY in prompt_text
            or "fake-jira-issue-canary-001" in prompt_text
            or "fake-jira-cloud-001" in prompt_text
            or "surfsense-e2e.atlassian.net" in prompt_text
        )
        has_slack_evidence = (
            SLACK_CANARY_CHANNEL in prompt_text
            or SLACK_CANARY_TOKEN in prompt_text
            or "C_FAKE_SLACK_CANARY" in prompt_text
            or "T_FAKE_SLACK_TEAM" in prompt_text
        )
        has_clickup_evidence = (
            CLICKUP_CANARY_TITLE in prompt_text
            or CLICKUP_CANARY_TOKEN in prompt_text
            or CLICKUP_CANARY_TASK_ID in prompt_text
        )
        has_manual_upload_md_evidence = (
            MANUAL_UPLOAD_MD_CANARY_FILE in prompt_text
            or MANUAL_UPLOAD_MD_CANARY_TOKEN in prompt_text
        )
        has_manual_upload_pdf_evidence = (
            MANUAL_UPLOAD_PDF_CANARY_FILE in prompt_text
            or MANUAL_UPLOAD_PDF_CANARY_TOKEN in prompt_text
        )

        if wants_clickup and has_clickup_evidence:
            return f"ClickUp content found: {CLICKUP_CANARY_TOKEN}"
        if wants_slack and has_slack_evidence:
            return f"Slack content found: {SLACK_CANARY_TOKEN}"
        if wants_jira and has_jira_evidence:
            return f"Jira content found: {JIRA_CANARY_TOKEN}"
        if wants_linear and has_linear_evidence:
            return f"Linear content found: {LINEAR_CANARY_TOKEN}"
        if wants_confluence and has_confluence_evidence:
            return f"Confluence content found: {CONFLUENCE_CANARY_TOKEN}"
        if wants_notion and has_notion_evidence:
            return f"Notion content found: {NOTION_CANARY_TOKEN}"
        if wants_calendar and has_calendar_evidence:
            return f"Calendar content found: {CALENDAR_CANARY_TOKEN}"
        if wants_gmail and has_gmail_evidence:
            return f"Gmail content found: {GMAIL_CANARY_TOKEN}"
        if wants_onedrive_pdf and has_onedrive_pdf_evidence:
            return f"OneDrive PDF content found: {ONEDRIVE_PDF_CANARY_TOKEN}"
        if wants_onedrive and has_onedrive_evidence:
            return f"OneDrive content found: {ONEDRIVE_CANARY_TOKEN}"
        if wants_dropbox_pdf and has_dropbox_pdf_evidence:
            return f"Dropbox PDF content found: {DROPBOX_PDF_CANARY_TOKEN}"
        if wants_dropbox and has_dropbox_evidence:
            return f"Dropbox content found: {DROPBOX_CANARY_TOKEN}"
        if wants_drive_pdf and has_native_drive_pdf_evidence:
            return f"Drive PDF content found: {DRIVE_PDF_CANARY_TOKEN}"
        if wants_drive_pdf and has_composio_drive_pdf_evidence:
            return f"Drive PDF content found: {COMPOSIO_DRIVE_PDF_CANARY_TOKEN}"
        if wants_drive and has_drive_evidence:
            return f"Drive content found: {DRIVE_CANARY_TOKEN}"
        if wants_manual_upload_pdf and has_manual_upload_pdf_evidence:
            return f"Manual upload PDF content found: {MANUAL_UPLOAD_PDF_CANARY_TOKEN}"
        if wants_manual_upload_md and has_manual_upload_md_evidence:
            return f"Manual upload MD content found: {MANUAL_UPLOAD_MD_CANARY_TOKEN}"
        if (
            has_notion_evidence
            and not has_confluence_evidence
            and not has_jira_evidence
            and not has_linear_evidence
            and not has_calendar_evidence
            and not has_gmail_evidence
            and not has_drive_evidence
            and not has_onedrive_evidence
            and not has_dropbox_evidence
            and not has_slack_evidence
            and not has_clickup_evidence
        ):
            return f"Notion content found: {NOTION_CANARY_TOKEN}"
        if (
            has_confluence_evidence
            and not has_jira_evidence
            and not has_linear_evidence
            and not has_notion_evidence
            and not has_calendar_evidence
            and not has_gmail_evidence
            and not has_drive_evidence
            and not has_onedrive_evidence
            and not has_dropbox_evidence
            and not has_slack_evidence
            and not has_clickup_evidence
        ):
            return f"Confluence content found: {CONFLUENCE_CANARY_TOKEN}"
        if (
            has_jira_evidence
            and not has_confluence_evidence
            and not has_linear_evidence
            and not has_notion_evidence
            and not has_calendar_evidence
            and not has_gmail_evidence
            and not has_drive_evidence
            and not has_onedrive_evidence
            and not has_dropbox_evidence
            and not has_slack_evidence
            and not has_clickup_evidence
        ):
            return f"Jira content found: {JIRA_CANARY_TOKEN}"
        if (
            has_linear_evidence
            and not has_confluence_evidence
            and not has_jira_evidence
            and not has_notion_evidence
            and not has_calendar_evidence
            and not has_gmail_evidence
            and not has_drive_evidence
            and not has_onedrive_evidence
            and not has_dropbox_evidence
            and not has_slack_evidence
            and not has_clickup_evidence
        ):
            return f"Linear content found: {LINEAR_CANARY_TOKEN}"
        if (
            has_calendar_evidence
            and not has_confluence_evidence
            and not has_jira_evidence
            and not has_linear_evidence
            and not has_notion_evidence
            and not has_gmail_evidence
            and not has_drive_evidence
            and not has_onedrive_evidence
            and not has_dropbox_evidence
            and not has_slack_evidence
            and not has_clickup_evidence
        ):
            return f"Calendar content found: {CALENDAR_CANARY_TOKEN}"
        if (
            has_gmail_evidence
            and not has_confluence_evidence
            and not has_jira_evidence
            and not has_linear_evidence
            and not has_notion_evidence
            and not has_drive_evidence
            and not has_onedrive_evidence
            and not has_dropbox_evidence
            and not has_slack_evidence
            and not has_clickup_evidence
        ):
            return f"Gmail content found: {GMAIL_CANARY_TOKEN}"
        if (
            has_onedrive_evidence
            and not has_confluence_evidence
            and not has_jira_evidence
            and not has_linear_evidence
            and not has_notion_evidence
            and not has_calendar_evidence
            and not has_gmail_evidence
            and not has_drive_evidence
            and not has_dropbox_evidence
            and not has_slack_evidence
            and not has_clickup_evidence
        ):
            return f"OneDrive content found: {ONEDRIVE_CANARY_TOKEN}"
        if (
            has_dropbox_evidence
            and not has_confluence_evidence
            and not has_jira_evidence
            and not has_linear_evidence
            and not has_notion_evidence
            and not has_calendar_evidence
            and not has_gmail_evidence
            and not has_drive_evidence
            and not has_onedrive_evidence
            and not has_slack_evidence
            and not has_clickup_evidence
        ):
            return f"Dropbox content found: {DROPBOX_CANARY_TOKEN}"
        if (
            has_drive_evidence
            and not has_confluence_evidence
            and not has_jira_evidence
            and not has_linear_evidence
            and not has_notion_evidence
            and not has_gmail_evidence
            and not has_onedrive_evidence
            and not has_dropbox_evidence
            and not has_slack_evidence
            and not has_clickup_evidence
        ):
            return f"Drive content found: {DRIVE_CANARY_TOKEN}"
        if (
            has_slack_evidence
            and not has_confluence_evidence
            and not has_jira_evidence
            and not has_linear_evidence
            and not has_notion_evidence
            and not has_calendar_evidence
            and not has_gmail_evidence
            and not has_drive_evidence
            and not has_onedrive_evidence
            and not has_dropbox_evidence
            and not has_clickup_evidence
        ):
            return f"Slack content found: {SLACK_CANARY_TOKEN}"
        if (
            has_clickup_evidence
            and not has_confluence_evidence
            and not has_jira_evidence
            and not has_linear_evidence
            and not has_notion_evidence
            and not has_calendar_evidence
            and not has_gmail_evidence
            and not has_drive_evidence
            and not has_onedrive_evidence
            and not has_dropbox_evidence
            and not has_slack_evidence
        ):
            return f"ClickUp content found: {CLICKUP_CANARY_TOKEN}"
        if (
            has_manual_upload_pdf_evidence
            and not has_confluence_evidence
            and not has_jira_evidence
            and not has_linear_evidence
            and not has_notion_evidence
            and not has_calendar_evidence
            and not has_gmail_evidence
            and not has_drive_evidence
            and not has_onedrive_evidence
            and not has_dropbox_evidence
            and not has_slack_evidence
            and not has_clickup_evidence
        ):
            return f"Manual upload PDF content found: {MANUAL_UPLOAD_PDF_CANARY_TOKEN}"
        if (
            has_manual_upload_md_evidence
            and not has_confluence_evidence
            and not has_jira_evidence
            and not has_linear_evidence
            and not has_notion_evidence
            and not has_calendar_evidence
            and not has_gmail_evidence
            and not has_drive_evidence
            and not has_onedrive_evidence
            and not has_dropbox_evidence
            and not has_slack_evidence
            and not has_clickup_evidence
        ):
            return f"Manual upload MD content found: {MANUAL_UPLOAD_MD_CANARY_TOKEN}"
        return NO_RELEVANT_CONTENT_SENTINEL

    def _tool_call_message_for(self, messages: list[BaseMessage]) -> AIMessage | None:
        latest_human = next(
            (
                _content_to_text(message.content)
                for message in reversed(messages)
                if message.type == "human"
            ),
            "",
        )
        latest_tool = _latest_tool_message(messages)
        latest_tool_name = getattr(latest_tool, "name", None)
        latest_tool_text = _content_to_text(latest_tool.content) if latest_tool else ""

        # Marker unique to a connector subagent's prompt: the main agent must
        # delegate via ``task``; only the subagent has connector tools registered.
        in_connector_subagent = (
            "connected-apps specialist" in _messages_to_text(messages)
        )

        # Main agent: delegate live-tool connector work to its subagent (which
        # then runs the real tools below). Indexed connectors are absent here.
        if not in_connector_subagent and latest_tool is None:
            connector_delegations = (
                ("gmail", ("gmail", "email", "message", GMAIL_CANARY_SUBJECT)),
                ("calendar", ("calendar", "event", "meeting", CALENDAR_CANARY_SUMMARY)),
                (
                    "jira",
                    (
                        "jira",
                        "atlassian",
                        JIRA_CANARY_SUMMARY,
                        JIRA_CANARY_KEY,
                        "surfsense-e2e.atlassian.net",
                        "fake-jira-cloud-001",
                    ),
                ),
                ("linear", ("linear", "issue", LINEAR_CANARY_TITLE)),
                ("slack", ("slack", SLACK_CANARY_TOKEN)),
                ("clickup", ("clickup", CLICKUP_CANARY_TITLE)),
                ("notion", ("notion", NOTION_CANARY_TITLE)),
                ("confluence", ("confluence", CONFLUENCE_CANARY_TITLE)),
            )
            # Every MCP-backed connector is now one ``mcp_discovery`` route; the
            # needle set only decides which canary the delegation targets.
            for connector_key, needles in connector_delegations:
                if _contains_any(latest_human, needles):
                    return AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "name": "task",
                                "args": {
                                    "subagent_type": "mcp_discovery",
                                    "description": latest_human,
                                },
                                "id": f"call_e2e_task_{connector_key}",
                            }
                        ],
                    )

        if (
            latest_tool_name == "search_gmail"
            and GMAIL_CANARY_MESSAGE_ID in latest_tool_text
        ):
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "read_gmail_email",
                        "args": {"message_id": GMAIL_CANARY_MESSAGE_ID},
                        "id": "call_e2e_read_gmail",
                    }
                ],
            )

        if latest_tool is None and _contains_any(
            latest_human,
            ("gmail", "email", "message", GMAIL_CANARY_SUBJECT),
        ):
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_gmail",
                        "args": {
                            "query": f"subject:{GMAIL_CANARY_SUBJECT}",
                            "max_results": 5,
                        },
                        "id": "call_e2e_search_gmail",
                    }
                ],
            )

        if latest_tool is None and _contains_any(
            latest_human,
            ("calendar", "event", "meeting", CALENDAR_CANARY_SUMMARY),
        ):
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_calendar_events",
                        "args": {
                            "start_date": "2026-05-07",
                            "end_date": "2026-05-21",
                            "max_results": 10,
                        },
                        "id": "call_e2e_search_calendar_events",
                    }
                ],
            )

        if latest_tool is None and _contains_any(
            latest_human,
            (
                "jira",
                "atlassian",
                JIRA_CANARY_SUMMARY,
                JIRA_CANARY_KEY,
                "surfsense-e2e.atlassian.net",
                "fake-jira-cloud-001",
            ),
        ):
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "searchJiraIssuesUsingJql",
                        "args": {
                            "jql": f'summary ~ "{JIRA_CANARY_SUMMARY}"',
                            "maxResults": 5,
                        },
                        "id": "call_e2e_search_jira_issues",
                    }
                ],
            )

        if latest_tool is None and _contains_any(
            latest_human,
            ("linear", "issue", LINEAR_CANARY_TITLE),
        ):
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "list_issues",
                        "args": {"query": LINEAR_CANARY_TITLE, "limit": 5},
                        "id": "call_e2e_list_linear_issues",
                    }
                ],
            )

        if latest_tool is None and _contains_any(
            latest_human,
            ("slack", SLACK_CANARY_TOKEN),
        ):
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "slack_search_channels",
                        "args": {"query": SLACK_CANARY_CHANNEL, "limit": 5},
                        "id": "call_e2e_search_slack_channels",
                    }
                ],
            )

        if latest_tool is None and _contains_any(
            latest_human,
            ("clickup", CLICKUP_CANARY_TITLE),
        ):
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "clickup_search",
                        "args": {"query": CLICKUP_CANARY_TITLE, "limit": 5},
                        "id": "call_e2e_search_clickup_tasks",
                    }
                ],
            )

        # Confluence check precedes Notion: the Confluence prompt also contains
        # the word "page", so Notion's needle omits it to avoid cross-matching.
        if latest_tool is None and _contains_any(
            latest_human,
            ("confluence", CONFLUENCE_CANARY_TITLE),
        ):
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "searchConfluenceUsingCql",
                        "args": {"cql": f'text ~ "{CONFLUENCE_CANARY_TITLE}"'},
                        "id": "call_e2e_search_confluence",
                    }
                ],
            )

        if latest_tool is None and _contains_any(
            latest_human,
            ("notion", NOTION_CANARY_TITLE),
        ):
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search",
                        "args": {"query": NOTION_CANARY_TITLE},
                        "id": "call_e2e_search_notion",
                    }
                ],
            )

        return None

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        del stop, run_manager, kwargs
        message = self._tool_call_message_for(messages) or AIMessage(
            content=self._response_for(messages), tool_calls=[]
        )
        return ChatResult(generations=[ChatGeneration(message=message)])

    async def _astream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        del stop, run_manager, kwargs
        tool_call_message = self._tool_call_message_for(messages)
        if tool_call_message:
            for tool_call in tool_call_message.tool_calls:
                yield ChatGenerationChunk(
                    message=AIMessageChunk(
                        content="",
                        tool_call_chunks=[
                            {
                                "name": tool_call["name"],
                                "args": json.dumps(tool_call["args"]),
                                "id": tool_call["id"],
                                "index": 0,
                            }
                        ],
                    )
                )
            return

        yield ChatGenerationChunk(
            message=AIMessageChunk(content=self._response_for(messages))
        )


def fake_create_chat_litellm_from_agent_config(
    *args: Any, **kwargs: Any
) -> FakeChatLLM:
    del args, kwargs
    return FakeChatLLM()


def fake_create_chat_litellm_from_config(*args: Any, **kwargs: Any) -> FakeChatLLM:
    del args, kwargs
    return FakeChatLLM()
