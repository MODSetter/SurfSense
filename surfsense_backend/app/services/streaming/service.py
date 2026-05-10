"""Composition root: bundles every formatter + a per-invocation emitter registry."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from . import envelope
from .emitter import Emitter, EmitterRegistry
from .events import (
    action_log,
    data,
    error,
    interrupt,
    lifecycle,
    reasoning,
    source,
    subagent_lifecycle,
    text,
    tool,
)


class StreamingService:
    def __init__(self) -> None:
        self._message_id: str | None = None
        self.emitter_registry = EmitterRegistry()

    @property
    def message_id(self) -> str | None:
        return self._message_id

    def begin_message(self, message_id: str | None = None) -> str:
        self._message_id = message_id or envelope.generate_message_id()
        return self._message_id

    @staticmethod
    def generate_text_id() -> str:
        return envelope.generate_text_id()

    @staticmethod
    def generate_reasoning_id() -> str:
        return envelope.generate_reasoning_id()

    @staticmethod
    def generate_tool_call_id() -> str:
        return envelope.generate_tool_call_id()

    @staticmethod
    def generate_subagent_run_id() -> str:
        return envelope.generate_subagent_run_id()

    @staticmethod
    def get_response_headers() -> dict[str, str]:
        return envelope.get_response_headers()

    @staticmethod
    def format_done() -> str:
        return envelope.format_done()

    def resolve_emitter(
        self,
        *,
        run_id: str | None,
        parent_ids: Iterable[str] | None,
    ) -> Emitter:
        return self.emitter_registry.resolve(run_id=run_id, parent_ids=parent_ids)

    def format_message_start(
        self,
        message_id: str | None = None,
        *,
        emitter: Emitter | None = None,
    ) -> str:
        chosen = self.begin_message(message_id)
        return lifecycle.format_message_start(chosen, emitter=emitter)

    def format_message_finish(self, *, emitter: Emitter | None = None) -> str:
        return lifecycle.format_message_finish(emitter=emitter)

    def format_step_start(self, *, emitter: Emitter | None = None) -> str:
        return lifecycle.format_step_start(emitter=emitter)

    def format_step_finish(self, *, emitter: Emitter | None = None) -> str:
        return lifecycle.format_step_finish(emitter=emitter)

    def format_text_start(self, text_id: str, *, emitter: Emitter | None = None) -> str:
        return text.format_text_start(text_id, emitter=emitter)

    def format_text_delta(
        self, text_id: str, delta: str, *, emitter: Emitter | None = None
    ) -> str:
        return text.format_text_delta(text_id, delta, emitter=emitter)

    def format_text_end(self, text_id: str, *, emitter: Emitter | None = None) -> str:
        return text.format_text_end(text_id, emitter=emitter)

    def format_reasoning_start(
        self, reasoning_id: str, *, emitter: Emitter | None = None
    ) -> str:
        return reasoning.format_reasoning_start(reasoning_id, emitter=emitter)

    def format_reasoning_delta(
        self,
        reasoning_id: str,
        delta: str,
        *,
        emitter: Emitter | None = None,
    ) -> str:
        return reasoning.format_reasoning_delta(reasoning_id, delta, emitter=emitter)

    def format_reasoning_end(
        self, reasoning_id: str, *, emitter: Emitter | None = None
    ) -> str:
        return reasoning.format_reasoning_end(reasoning_id, emitter=emitter)

    def format_tool_input_start(
        self,
        tool_call_id: str,
        tool_name: str,
        *,
        langchain_tool_call_id: str | None = None,
        emitter: Emitter | None = None,
    ) -> str:
        return tool.format_tool_input_start(
            tool_call_id,
            tool_name,
            langchain_tool_call_id=langchain_tool_call_id,
            emitter=emitter,
        )

    def format_tool_input_delta(
        self,
        tool_call_id: str,
        input_text_delta: str,
        *,
        emitter: Emitter | None = None,
    ) -> str:
        return tool.format_tool_input_delta(
            tool_call_id, input_text_delta, emitter=emitter
        )

    def format_tool_input_available(
        self,
        tool_call_id: str,
        tool_name: str,
        input_data: dict[str, Any],
        *,
        langchain_tool_call_id: str | None = None,
        emitter: Emitter | None = None,
    ) -> str:
        return tool.format_tool_input_available(
            tool_call_id,
            tool_name,
            input_data,
            langchain_tool_call_id=langchain_tool_call_id,
            emitter=emitter,
        )

    def format_tool_output_available(
        self,
        tool_call_id: str,
        output: Any,
        *,
        langchain_tool_call_id: str | None = None,
        emitter: Emitter | None = None,
    ) -> str:
        return tool.format_tool_output_available(
            tool_call_id,
            output,
            langchain_tool_call_id=langchain_tool_call_id,
            emitter=emitter,
        )

    def format_source_url(
        self,
        url: str,
        *,
        source_id: str | None = None,
        title: str | None = None,
        emitter: Emitter | None = None,
    ) -> str:
        return source.format_source_url(
            url, source_id=source_id, title=title, emitter=emitter
        )

    def format_source_document(
        self,
        source_id: str,
        *,
        media_type: str = "file",
        title: str | None = None,
        description: str | None = None,
        emitter: Emitter | None = None,
    ) -> str:
        return source.format_source_document(
            source_id,
            media_type=media_type,
            title=title,
            description=description,
            emitter=emitter,
        )

    def format_file(
        self, url: str, media_type: str, *, emitter: Emitter | None = None
    ) -> str:
        return source.format_file(url, media_type, emitter=emitter)

    def format_data(
        self, data_type: str, payload: Any, *, emitter: Emitter | None = None
    ) -> str:
        return data.format_data(data_type, payload, emitter=emitter)

    def format_terminal_info(
        self,
        text_value: str,
        *,
        message_type: str = "info",
        emitter: Emitter | None = None,
    ) -> str:
        return data.format_terminal_info(
            text_value, message_type=message_type, emitter=emitter
        )

    def format_further_questions(
        self,
        questions: list[str],
        *,
        emitter: Emitter | None = None,
    ) -> str:
        return data.format_further_questions(questions, emitter=emitter)

    def format_thinking_step(
        self,
        *,
        step_id: str,
        title: str,
        status: str = "in_progress",
        items: list[str] | None = None,
        emitter: Emitter | None = None,
    ) -> str:
        return data.format_thinking_step(
            step_id=step_id,
            title=title,
            status=status,
            items=items,
            emitter=emitter,
        )

    def format_thread_title_update(
        self,
        *,
        thread_id: int,
        title: str,
        emitter: Emitter | None = None,
    ) -> str:
        return data.format_thread_title_update(
            thread_id=thread_id, title=title, emitter=emitter
        )

    def format_turn_info(
        self,
        *,
        chat_turn_id: str,
        emitter: Emitter | None = None,
    ) -> str:
        return data.format_turn_info(chat_turn_id=chat_turn_id, emitter=emitter)

    def format_turn_status(
        self,
        *,
        status: str,
        emitter: Emitter | None = None,
    ) -> str:
        return data.format_turn_status(status=status, emitter=emitter)

    def format_user_message_id(
        self,
        *,
        message_id: str,
        turn_id: str,
        emitter: Emitter | None = None,
    ) -> str:
        return data.format_user_message_id(
            message_id=message_id, turn_id=turn_id, emitter=emitter
        )

    def format_assistant_message_id(
        self,
        *,
        message_id: str,
        turn_id: str,
        emitter: Emitter | None = None,
    ) -> str:
        return data.format_assistant_message_id(
            message_id=message_id, turn_id=turn_id, emitter=emitter
        )

    def format_error(
        self,
        error_text: str,
        *,
        error_code: str | None = None,
        extra: dict[str, Any] | None = None,
        emitter: Emitter | None = None,
    ) -> str:
        return error.format_error(
            error_text,
            error_code=error_code,
            extra=extra,
            emitter=emitter,
        )

    def format_interrupt_request(
        self,
        interrupt_value: dict[str, Any],
        *,
        interrupt_id: str | None = None,
        pending_interrupt_count: int | None = None,
        chat_turn_id: str | None = None,
        emitter: Emitter | None = None,
    ) -> str:
        return interrupt.format_interrupt_request(
            interrupt_value,
            interrupt_id=interrupt_id,
            pending_interrupt_count=pending_interrupt_count,
            chat_turn_id=chat_turn_id,
            emitter=emitter,
        )

    def format_subagent_start(
        self,
        *,
        subagent_run_id: str,
        subagent_type: str,
        parent_tool_call_id: str,
        chat_turn_id: str | None = None,
        description: str | None = None,
        started_at: str | None = None,
        emitter: Emitter | None = None,
    ) -> str:
        return subagent_lifecycle.format_subagent_start(
            subagent_run_id=subagent_run_id,
            subagent_type=subagent_type,
            parent_tool_call_id=parent_tool_call_id,
            chat_turn_id=chat_turn_id,
            description=description,
            started_at=started_at,
            emitter=emitter,
        )

    def format_subagent_finish(
        self,
        *,
        subagent_run_id: str,
        subagent_type: str,
        parent_tool_call_id: str,
        status: str = "completed",
        ended_at: str | None = None,
        duration_ms: int | None = None,
        emitter: Emitter | None = None,
    ) -> str:
        return subagent_lifecycle.format_subagent_finish(
            subagent_run_id=subagent_run_id,
            subagent_type=subagent_type,
            parent_tool_call_id=parent_tool_call_id,
            status=status,
            ended_at=ended_at,
            duration_ms=duration_ms,
            emitter=emitter,
        )

    def format_subagent_error(
        self,
        *,
        subagent_run_id: str,
        subagent_type: str,
        parent_tool_call_id: str,
        error_text: str,
        error_type: str | None = None,
        ended_at: str | None = None,
        duration_ms: int | None = None,
        emitter: Emitter | None = None,
    ) -> str:
        return subagent_lifecycle.format_subagent_error(
            subagent_run_id=subagent_run_id,
            subagent_type=subagent_type,
            parent_tool_call_id=parent_tool_call_id,
            error_text=error_text,
            error_type=error_type,
            ended_at=ended_at,
            duration_ms=duration_ms,
            emitter=emitter,
        )

    def format_action_log(
        self,
        payload: dict[str, Any],
        *,
        emitter: Emitter | None = None,
    ) -> str:
        return action_log.format_action_log(payload, emitter=emitter)

    def format_action_log_updated(
        self,
        payload: dict[str, Any],
        *,
        emitter: Emitter | None = None,
    ) -> str:
        return action_log.format_action_log_updated(payload, emitter=emitter)
