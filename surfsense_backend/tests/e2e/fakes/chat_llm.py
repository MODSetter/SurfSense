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
GMAIL_CANARY_TOKEN = "SURFSENSE_E2E_CANARY_TOKEN_GMAIL_001"
GMAIL_CANARY_SUBJECT = "E2E Canary Email"
GMAIL_CANARY_MESSAGE_ID = "fake-msg-canary-001"
CALENDAR_CANARY_TOKEN = "SURFSENSE_E2E_CANARY_TOKEN_CALENDAR_001"
CALENDAR_CANARY_SUMMARY = "E2E Canary Calendar Event"
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
    return next((message for message in reversed(messages) if message.type == "tool"), None)


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

        if latest_tool_name == "read_gmail_email" and GMAIL_CANARY_TOKEN in latest_tool_text:
            return f"Gmail live tool content found: {GMAIL_CANARY_TOKEN}"
        if latest_tool_name == "search_gmail" and GMAIL_CANARY_MESSAGE_ID in latest_tool_text:
            return "Reading the matching Gmail message next."
        if (
            latest_tool_name == "search_calendar_events"
            and CALENDAR_CANARY_TOKEN in latest_tool_text
        ):
            return f"Calendar live tool content found: {CALENDAR_CANARY_TOKEN}"

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
        has_gmail_evidence = (
            GMAIL_CANARY_SUBJECT in prompt_text
            or GMAIL_CANARY_MESSAGE_ID in prompt_text
            or GMAIL_CANARY_TOKEN in prompt_text
        )
        has_calendar_evidence = (
            CALENDAR_CANARY_SUMMARY in prompt_text or CALENDAR_CANARY_TOKEN in prompt_text
        )
        has_drive_evidence = (
            "e2e-canary.txt" in prompt_text
            or "fake-file-canary" in prompt_text
            or DRIVE_CANARY_TOKEN in prompt_text
        )

        if wants_calendar and has_calendar_evidence:
            return f"Calendar content found: {CALENDAR_CANARY_TOKEN}"
        if wants_gmail and has_gmail_evidence:
            return f"Gmail content found: {GMAIL_CANARY_TOKEN}"
        if wants_drive and has_drive_evidence:
            return f"Drive content found: {DRIVE_CANARY_TOKEN}"
        if has_calendar_evidence and not has_gmail_evidence and not has_drive_evidence:
            return f"Calendar content found: {CALENDAR_CANARY_TOKEN}"
        if has_gmail_evidence and not has_drive_evidence:
            return f"Gmail content found: {GMAIL_CANARY_TOKEN}"
        if has_drive_evidence and not has_gmail_evidence:
            return f"Drive content found: {DRIVE_CANARY_TOKEN}"
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

        if latest_tool_name == "search_gmail" and GMAIL_CANARY_MESSAGE_ID in latest_tool_text:
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


def fake_create_chat_litellm_from_agent_config(*args: Any, **kwargs: Any) -> FakeChatLLM:
    del args, kwargs
    return FakeChatLLM()


def fake_create_chat_litellm_from_config(*args: Any, **kwargs: Any) -> FakeChatLLM:
    del args, kwargs
    return FakeChatLLM()
