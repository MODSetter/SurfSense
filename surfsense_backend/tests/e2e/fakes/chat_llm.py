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
        wants_gmail = _contains_any(
            latest_human,
            ("gmail", "email", "message", "E2E Canary Email"),
        )
        wants_drive = _contains_any(
            latest_human,
            ("drive", "file", "e2e-canary.txt"),
        )
        has_gmail_evidence = (
            "E2E Canary Email" in prompt_text
            or "fake-msg-canary-001" in prompt_text
            or GMAIL_CANARY_TOKEN in prompt_text
        )
        has_drive_evidence = (
            "e2e-canary.txt" in prompt_text
            or "fake-file-canary" in prompt_text
            or DRIVE_CANARY_TOKEN in prompt_text
        )

        if wants_gmail and has_gmail_evidence:
            return f"Gmail content found: {GMAIL_CANARY_TOKEN}"
        if wants_drive and has_drive_evidence:
            return f"Drive content found: {DRIVE_CANARY_TOKEN}"
        if has_gmail_evidence and not has_drive_evidence:
            return f"Gmail content found: {GMAIL_CANARY_TOKEN}"
        if has_drive_evidence and not has_gmail_evidence:
            return f"Drive content found: {DRIVE_CANARY_TOKEN}"
        return NO_RELEVANT_CONTENT_SENTINEL

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        del stop, run_manager, kwargs
        message = AIMessage(content=self._response_for(messages), tool_calls=[])
        return ChatResult(generations=[ChatGeneration(message=message)])

    async def _astream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        del stop, run_manager, kwargs
        yield ChatGenerationChunk(
            message=AIMessageChunk(content=self._response_for(messages))
        )


def fake_create_chat_litellm_from_agent_config(*args: Any, **kwargs: Any) -> FakeChatLLM:
    del args, kwargs
    return FakeChatLLM()


def fake_create_chat_litellm_from_config(*args: Any, **kwargs: Any) -> FakeChatLLM:
    del args, kwargs
    return FakeChatLLM()
