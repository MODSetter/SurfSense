"""
Streaming task for the new SurfSense deep agent chat.

This module streams responses from the deep agent using the Vercel AI SDK
Data Stream Protocol (SSE format).

Supports loading LLM configurations from:
- YAML files (negative IDs for global configs)
- NewLLMConfig database table (positive IDs for user-created configs with prompt settings)
"""

import ast
import asyncio
import contextlib
import gc
import json
import logging
import re
import time
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from functools import partial
from typing import Any, Literal
from uuid import UUID

import anyio
from langchain_core.messages import HumanMessage
from sqlalchemy import func
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.agents.new_chat.chat_deepagent import create_surfsense_deep_agent
from app.agents.new_chat.checkpointer import get_checkpointer
from app.agents.new_chat.errors import BusyError
from app.agents.new_chat.feature_flags import get_flags
from app.agents.new_chat.filesystem_selection import FilesystemMode, FilesystemSelection
from app.agents.new_chat.llm_config import (
    AgentConfig,
    create_chat_litellm_from_agent_config,
    create_chat_litellm_from_config,
    load_agent_config,
    load_global_llm_config_by_id,
)
from app.agents.new_chat.memory_extraction import (
    extract_and_save_memory,
    extract_and_save_team_memory,
)
from app.agents.new_chat.middleware.busy_mutex import (
    end_turn,
    get_cancel_state,
    is_cancel_requested,
)
from app.agents.new_chat.middleware.kb_persistence import (
    commit_staged_filesystem_state,
)
from app.db import (
    ChatVisibility,
    NewChatMessage,
    NewChatThread,
    Report,
    SearchSourceConnectorType,
    SurfsenseDocsDocument,
    async_session_maker,
    shielded_async_session,
)
from app.prompts import TITLE_GENERATION_PROMPT
from app.services.auto_model_pin_service import (
    mark_runtime_cooldown,
    resolve_or_get_pinned_llm_config_id,
)
from app.services.chat_session_state_service import (
    clear_ai_responding,
    set_ai_responding,
)
from app.services.connector_service import ConnectorService
from app.services.new_streaming_service import VercelStreamingService
from app.utils.content_utils import bootstrap_history_from_db
from app.utils.perf import get_perf_logger, log_system_snapshot, trim_native_heap
from app.utils.user_message_multimodal import build_human_message_content

_background_tasks: set[asyncio.Task] = set()
_perf_log = get_perf_logger()
TURN_CANCELLING_INITIAL_DELAY_MS = 200
TURN_CANCELLING_BACKOFF_FACTOR = 2
TURN_CANCELLING_MAX_DELAY_MS = 1500


def _compute_turn_cancelling_retry_delay(attempt: int) -> int:
    if attempt < 1:
        attempt = 1
    delay = TURN_CANCELLING_INITIAL_DELAY_MS * (
        TURN_CANCELLING_BACKOFF_FACTOR ** (attempt - 1)
    )
    return min(delay, TURN_CANCELLING_MAX_DELAY_MS)


def _extract_chunk_parts(chunk: Any) -> dict[str, Any]:
    """Decompose an ``AIMessageChunk`` into typed text/reasoning/tool-call parts.

    Returns a dict with three keys:

    * ``text`` — concatenated string content (empty string if the chunk
      contributes none).
    * ``reasoning`` — concatenated reasoning content (empty string if the
      chunk contributes none).
    * ``tool_call_chunks`` — flat list of LangChain ``tool_call_chunk``
      dicts surfaced from either the typed-block list or the
      ``tool_call_chunks`` attribute.

    Background
    ----------
    ``AIMessageChunk.content`` can be:

    * a ``str`` (most providers), or
    * a ``list`` of typed blocks ``{type: 'text' | 'reasoning' |
      'tool_call_chunk' | 'tool_use' | ..., text/content/...}`` for
      Anthropic, Bedrock, and several reasoning configurations.

    Reasoning may also live under
    ``chunk.additional_kwargs['reasoning_content']`` (some providers
    surface it that way instead of as a typed block). Tool-call chunks
    may live under ``chunk.tool_call_chunks`` even when ``content`` is a
    plain string.

    Earlier versions only handled the ``isinstance(content, str)`` branch
    and silently dropped reasoning blocks + tool-call chunks emitted by
    LangChain ``AIMessageChunk``s.
    """
    out: dict[str, Any] = {"text": "", "reasoning": "", "tool_call_chunks": []}
    if chunk is None:
        return out

    content = getattr(chunk, "content", None)
    if isinstance(content, str):
        if content:
            out["text"] = content
    elif isinstance(content, list):
        text_parts: list[str] = []
        reasoning_parts: list[str] = []
        for block in content:
            if not isinstance(block, dict):
                continue
            block_type = block.get("type")
            if block_type == "text":
                value = block.get("text") or block.get("content") or ""
                if isinstance(value, str) and value:
                    text_parts.append(value)
            elif block_type == "reasoning":
                value = (
                    block.get("reasoning")
                    or block.get("text")
                    or block.get("content")
                    or ""
                )
                if isinstance(value, str) and value:
                    reasoning_parts.append(value)
            elif block_type in ("tool_call_chunk", "tool_use"):
                out["tool_call_chunks"].append(block)
        if text_parts:
            out["text"] = "".join(text_parts)
        if reasoning_parts:
            out["reasoning"] = "".join(reasoning_parts)

    additional = getattr(chunk, "additional_kwargs", None) or {}
    if isinstance(additional, dict):
        extra_reasoning = additional.get("reasoning_content")
        if isinstance(extra_reasoning, str) and extra_reasoning:
            existing = out["reasoning"]
            out["reasoning"] = (
                (existing + extra_reasoning) if existing else extra_reasoning
            )

    extra_tool_chunks = getattr(chunk, "tool_call_chunks", None)
    if isinstance(extra_tool_chunks, list):
        for tcc in extra_tool_chunks:
            if isinstance(tcc, dict):
                out["tool_call_chunks"].append(tcc)

    return out


def format_mentioned_surfsense_docs_as_context(
    documents: list[SurfsenseDocsDocument],
) -> str:
    """Format mentioned SurfSense documentation as context for the agent."""
    if not documents:
        return ""

    context_parts = ["<mentioned_surfsense_docs>"]
    context_parts.append(
        "The user has explicitly mentioned the following SurfSense documentation pages. "
        "These are official documentation about how to use SurfSense and should be used to answer questions about the application. "
        "Use [citation:CHUNK_ID] format for citations (e.g., [citation:doc-123])."
    )

    for doc in documents:
        metadata_json = json.dumps({"source": doc.source}, ensure_ascii=False)

        context_parts.append("<document>")
        context_parts.append("<document_metadata>")
        context_parts.append(f"  <document_id>doc-{doc.id}</document_id>")
        context_parts.append("  <document_type>SURFSENSE_DOCS</document_type>")
        context_parts.append(f"  <title><![CDATA[{doc.title}]]></title>")
        context_parts.append(f"  <url><![CDATA[{doc.source}]]></url>")
        context_parts.append(
            f"  <metadata_json><![CDATA[{metadata_json}]]></metadata_json>"
        )
        context_parts.append("</document_metadata>")
        context_parts.append("")
        context_parts.append("<document_content>")

        if hasattr(doc, "chunks") and doc.chunks:
            for chunk in doc.chunks:
                context_parts.append(
                    f"  <chunk id='doc-{chunk.id}'><![CDATA[{chunk.content}]]></chunk>"
                )
        else:
            context_parts.append(
                f"  <chunk id='doc-0'><![CDATA[{doc.content}]]></chunk>"
            )

        context_parts.append("</document_content>")
        context_parts.append("</document>")
        context_parts.append("")

    context_parts.append("</mentioned_surfsense_docs>")

    return "\n".join(context_parts)


def extract_todos_from_deepagents(command_output) -> dict:
    """
    Extract todos from deepagents' TodoListMiddleware Command output.

    deepagents returns a Command object with:
    - Command.update['todos'] = [{'content': '...', 'status': '...'}]

    Returns the todos directly (no transformation needed - UI matches deepagents format).
    """
    todos_data = []
    if hasattr(command_output, "update"):
        # It's a Command object from deepagents
        update = command_output.update
        todos_data = update.get("todos", [])
    elif isinstance(command_output, dict):
        # Already a dict - check if it has todos directly or in update
        if "todos" in command_output:
            todos_data = command_output.get("todos", [])
        elif "update" in command_output and isinstance(command_output["update"], dict):
            todos_data = command_output["update"].get("todos", [])

    return {"todos": todos_data}


@dataclass
class StreamResult:
    accumulated_text: str = ""
    is_interrupted: bool = False
    interrupt_value: dict[str, Any] | None = None
    sandbox_files: list[str] = field(default_factory=list)
    agent_called_update_memory: bool = False
    request_id: str | None = None
    turn_id: str = ""
    filesystem_mode: str = "cloud"
    client_platform: str = "web"
    intent_detected: str = "chat_only"
    intent_confidence: float = 0.0
    write_attempted: bool = False
    write_succeeded: bool = False
    verification_succeeded: bool = False
    commit_gate_passed: bool = True
    commit_gate_reason: str = ""


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _tool_output_to_text(tool_output: Any) -> str:
    if isinstance(tool_output, dict):
        if isinstance(tool_output.get("result"), str):
            return tool_output["result"]
        if isinstance(tool_output.get("error"), str):
            return tool_output["error"]
        return json.dumps(tool_output, ensure_ascii=False)
    return str(tool_output)


def _tool_output_has_error(tool_output: Any) -> bool:
    if isinstance(tool_output, dict):
        if tool_output.get("error"):
            return True
        result = tool_output.get("result")
        return bool(
            isinstance(result, str) and result.strip().lower().startswith("error:")
        )
    if isinstance(tool_output, str):
        return tool_output.strip().lower().startswith("error:")
    return False


def _extract_resolved_file_path(*, tool_name: str, tool_output: Any) -> str | None:
    if isinstance(tool_output, dict):
        path_value = tool_output.get("path")
        if isinstance(path_value, str) and path_value.strip():
            return path_value.strip()
    text = _tool_output_to_text(tool_output)
    if tool_name == "write_file":
        match = re.search(r"Updated file\s+(.+)$", text.strip())
        if match:
            return match.group(1).strip()
    if tool_name == "edit_file":
        match = re.search(r"in '([^']+)'", text)
        if match:
            return match.group(1).strip()
    return None


def _contract_enforcement_active(result: StreamResult) -> bool:
    # Keep policy deterministic with no env-driven progression modes:
    # enforce the file-operation contract only in desktop local-folder mode.
    return result.filesystem_mode == "desktop_local_folder"


def _evaluate_file_contract_outcome(result: StreamResult) -> tuple[bool, str]:
    if result.intent_detected != "file_write":
        return True, ""
    if not result.write_attempted:
        return False, "no_write_attempt"
    if not result.write_succeeded:
        return False, "write_failed"
    if not result.verification_succeeded:
        return False, "verification_failed"
    return True, ""


def _log_file_contract(stage: str, result: StreamResult, **extra: Any) -> None:
    payload: dict[str, Any] = {
        "stage": stage,
        "request_id": result.request_id or "unknown",
        "turn_id": result.turn_id or "unknown",
        "chat_id": result.turn_id.split(":", 1)[0]
        if ":" in result.turn_id
        else "unknown",
        "filesystem_mode": result.filesystem_mode,
        "client_platform": result.client_platform,
        "intent_detected": result.intent_detected,
        "intent_confidence": result.intent_confidence,
        "write_attempted": result.write_attempted,
        "write_succeeded": result.write_succeeded,
        "verification_succeeded": result.verification_succeeded,
        "commit_gate_passed": result.commit_gate_passed,
        "commit_gate_reason": result.commit_gate_reason or None,
    }
    payload.update(extra)
    _perf_log.info(
        "[file_operation_contract] %s", json.dumps(payload, ensure_ascii=False)
    )


def _log_chat_stream_error(
    *,
    flow: Literal["new", "resume", "regenerate"],
    error_kind: str,
    error_code: str | None,
    severity: Literal["info", "warn", "error"],
    is_expected: bool,
    request_id: str | None,
    thread_id: int | None,
    search_space_id: int | None,
    user_id: str | None,
    message: str,
    extra: dict[str, Any] | None = None,
) -> None:
    payload: dict[str, Any] = {
        "event": "chat_stream_error",
        "flow": flow,
        "error_kind": error_kind,
        "error_code": error_code,
        "severity": severity,
        "is_expected": is_expected,
        "request_id": request_id or "unknown",
        "thread_id": thread_id,
        "search_space_id": search_space_id,
        "user_id": user_id,
        "message": message,
    }
    if extra:
        payload.update(extra)

    logger = logging.getLogger(__name__)
    rendered = json.dumps(payload, ensure_ascii=False)
    if severity == "error":
        logger.error("[chat_stream_error] %s", rendered)
    elif severity == "warn":
        logger.warning("[chat_stream_error] %s", rendered)
    else:
        logger.info("[chat_stream_error] %s", rendered)


def _parse_error_payload(message: str) -> dict[str, Any] | None:
    candidates = [message]
    first_brace_idx = message.find("{")
    if first_brace_idx >= 0:
        candidates.append(message[first_brace_idx:])

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            continue
    return None


def _extract_provider_error_code(parsed: dict[str, Any] | None) -> int | None:
    if not isinstance(parsed, dict):
        return None
    candidates: list[Any] = [parsed.get("code")]
    nested = parsed.get("error")
    if isinstance(nested, dict):
        candidates.append(nested.get("code"))
    for value in candidates:
        try:
            if value is None:
                continue
            return int(value)
        except Exception:
            continue
    return None


def _is_provider_rate_limited(exc: BaseException) -> bool:
    """Best-effort detection for provider-side runtime throttling.

    Covers LiteLLM/OpenRouter shapes like:
    - class name contains ``RateLimit``
    - nested payload ``{"error": {"code": 429}}``
    - nested payload ``{"error": {"type": "rate_limit_error"}}``
    """
    raw = str(exc)
    lowered = raw.lower()
    if "ratelimit" in type(exc).__name__.lower():
        return True
    parsed = _parse_error_payload(raw)
    provider_code = _extract_provider_error_code(parsed)
    if provider_code == 429:
        return True

    provider_error_type = ""
    if parsed:
        top_type = parsed.get("type")
        if isinstance(top_type, str):
            provider_error_type = top_type.lower()
        nested = parsed.get("error")
        if isinstance(nested, dict):
            nested_type = nested.get("type")
            if isinstance(nested_type, str):
                provider_error_type = nested_type.lower()
    if provider_error_type == "rate_limit_error":
        return True

    return (
        "rate limited" in lowered
        or "rate-limited" in lowered
        or "temporarily rate-limited upstream" in lowered
    )


def _classify_stream_exception(
    exc: Exception,
    *,
    flow_label: str,
) -> tuple[
    str, str, Literal["info", "warn", "error"], bool, str, dict[str, Any] | None
]:
    raw = str(exc)
    if isinstance(exc, BusyError) or "Thread is busy with another request" in raw:
        busy_thread_id = str(exc.request_id) if isinstance(exc, BusyError) else None
        if busy_thread_id and is_cancel_requested(busy_thread_id):
            cancel_state = get_cancel_state(busy_thread_id)
            attempt = cancel_state[0] if cancel_state else 1
            retry_after_ms = _compute_turn_cancelling_retry_delay(attempt)
            retry_after_at = int(time.time() * 1000) + retry_after_ms
            return (
                "thread_busy",
                "TURN_CANCELLING",
                "info",
                True,
                "A previous response is still stopping. Please try again in a moment.",
                {
                    "retry_after_ms": retry_after_ms,
                    "retry_after_at": retry_after_at,
                },
            )
        return (
            "thread_busy",
            "THREAD_BUSY",
            "warn",
            True,
            "Another response is still finishing for this thread. Please try again in a moment.",
            None,
        )

    if _is_provider_rate_limited(exc):
        return (
            "rate_limited",
            "RATE_LIMITED",
            "warn",
            True,
            "This model is temporarily rate-limited. Please try again in a few seconds or switch models.",
            None,
        )

    return (
        "server_error",
        "SERVER_ERROR",
        "error",
        False,
        f"Error during {flow_label}: {raw}",
        None,
    )


def _emit_stream_terminal_error(
    *,
    streaming_service: VercelStreamingService,
    flow: str,
    request_id: str | None,
    thread_id: int,
    search_space_id: int,
    user_id: str | None,
    message: str,
    error_kind: str = "server_error",
    error_code: str = "SERVER_ERROR",
    severity: Literal["info", "warn", "error"] = "error",
    is_expected: bool = False,
    extra: dict[str, Any] | None = None,
) -> str:
    _log_chat_stream_error(
        flow=flow,
        error_kind=error_kind,
        error_code=error_code,
        severity=severity,
        is_expected=is_expected,
        request_id=request_id,
        thread_id=thread_id,
        search_space_id=search_space_id,
        user_id=user_id,
        message=message,
        extra=extra,
    )
    return streaming_service.format_error(message, error_code=error_code, extra=extra)


def _legacy_match_lc_id(
    pending_tool_call_chunks: list[dict[str, Any]],
    tool_name: str,
    run_id: str,
    lc_tool_call_id_by_run: dict[str, str],
) -> str | None:
    """Best-effort match a buffered ``tool_call_chunk`` to a tool name.

    Pure extract of the legacy in-line match used at ``on_tool_start`` for
    parity_v2-OFF and unmatched (chunk path didn't register an index for
    this call) tools. Pops the next id-bearing chunk whose ``name``
    matches ``tool_name`` (or any id-bearing chunk as a fallback) and
    returns its id. Mutates ``pending_tool_call_chunks`` and
    ``lc_tool_call_id_by_run`` in place.
    """
    matched_idx: int | None = None
    for idx, tcc in enumerate(pending_tool_call_chunks):
        if tcc.get("name") == tool_name and tcc.get("id"):
            matched_idx = idx
            break
    if matched_idx is None:
        for idx, tcc in enumerate(pending_tool_call_chunks):
            if tcc.get("id"):
                matched_idx = idx
                break
    if matched_idx is None:
        return None
    matched = pending_tool_call_chunks.pop(matched_idx)
    candidate = matched.get("id")
    if isinstance(candidate, str) and candidate:
        if run_id:
            lc_tool_call_id_by_run[run_id] = candidate
        return candidate
    return None


async def _stream_agent_events(
    agent: Any,
    config: dict[str, Any],
    input_data: Any,
    streaming_service: VercelStreamingService,
    result: StreamResult,
    step_prefix: str = "thinking",
    initial_step_id: str | None = None,
    initial_step_title: str = "",
    initial_step_items: list[str] | None = None,
    *,
    fallback_commit_search_space_id: int | None = None,
    fallback_commit_created_by_id: str | None = None,
    fallback_commit_filesystem_mode: FilesystemMode = FilesystemMode.CLOUD,
    fallback_commit_thread_id: int | None = None,
) -> AsyncGenerator[str, None]:
    """Shared async generator that streams and formats astream_events from the agent.

    Yields SSE-formatted strings. After exhausting, inspect the ``result``
    object for accumulated_text and interrupt state.

    Args:
        agent: The compiled LangGraph agent.
        config: LangGraph config dict (must include configurable.thread_id).
        input_data: The input to pass to agent.astream_events (dict or Command).
        streaming_service: VercelStreamingService instance for formatting events.
        result: Mutable StreamResult populated with accumulated_text / interrupt info.
        step_prefix: Prefix for thinking step IDs (e.g. "thinking" or "thinking-resume").
        initial_step_id: If set, the helper inherits an already-active thinking step.
        initial_step_title: Title of the inherited thinking step.
        initial_step_items: Items of the inherited thinking step.

    Yields:
        SSE-formatted strings for each event.
    """
    accumulated_text = ""
    current_text_id: str | None = None
    thinking_step_counter = 1 if initial_step_id else 0
    tool_step_ids: dict[str, str] = {}
    completed_step_ids: set[str] = set()
    last_active_step_id: str | None = initial_step_id
    last_active_step_title: str = initial_step_title
    last_active_step_items: list[str] = initial_step_items or []
    just_finished_tool: bool = False
    active_tool_depth: int = 0  # Track nesting: >0 means we're inside a tool
    called_update_memory: bool = False

    # Reasoning-block streaming. We open a reasoning block on the
    # first reasoning delta of a step, append deltas as they arrive, and
    # close it when text starts (the model has switched to writing its
    # answer) or ``on_chat_model_end`` fires for the model node. Reuses
    # the same Vercel format-helpers as text-start/delta/end.
    current_reasoning_id: str | None = None

    # Streaming-parity v2 feature flag. When OFF we keep the legacy
    # shape: str-only content, no reasoning blocks, no
    # ``langchainToolCallId`` propagation. The schema migrations
    # (135 / 136) ship unconditionally because they're forward-compatible.
    parity_v2 = bool(get_flags().enable_stream_parity_v2)

    # Best-effort attach of LangChain ``tool_call_id`` to the synthetic
    # ``call_<run_id>`` card id we already emit. We accumulate
    # ``tool_call_chunks`` from ``on_chat_model_stream``, key them by
    # name, and pop the next unconsumed entry at ``on_tool_start``. The
    # authoritative id is later filled in at ``on_tool_end`` from
    # ``ToolMessage.tool_call_id``. Under parity_v2 we ALSO short-circuit
    # this list for chunks that already registered into ``index_to_meta``
    # below — so this list is reserved for the parity_v2-OFF / unmatched
    # fallback path only and never re-pops a chunk we already streamed.
    pending_tool_call_chunks: list[dict[str, Any]] = []
    lc_tool_call_id_by_run: dict[str, str] = {}

    # parity_v2 only: live tool-call argument streaming. ``index_to_meta``
    # is keyed by the chunk's ``index`` field — LangChain
    # ``ToolCallChunk``s for the same call share an index but only the
    # first chunk carries id+name (subsequent ones are id=None,
    # name=None, args="<delta>"). We register an index when both id and
    # name are observed on a chunk (per ToolCallChunk semantics they
    # arrive together on the first chunk), then route every later chunk
    # at that index to the same ``ui_id`` as a ``tool-input-delta``.
    # ``ui_tool_call_id_by_run`` maps LangGraph ``run_id`` to the
    # ``ui_id`` used for that call's ``tool-input-start`` so the matching
    # ``tool-output-available`` (emitted from ``on_tool_end``) lands on
    # the same card.
    index_to_meta: dict[int, dict[str, str]] = {}
    ui_tool_call_id_by_run: dict[str, str] = {}

    # Per-tool-end mutable cache for the LangChain tool_call_id resolved
    # at ``on_tool_end``. ``_emit_tool_output`` reads this so every
    # ``format_tool_output_available`` call automatically carries the
    # authoritative id without duplicating the kwarg at every call site.
    current_lc_tool_call_id: dict[str, str | None] = {"value": None}

    def _emit_tool_output(call_id: str, output: Any) -> str:
        return streaming_service.format_tool_output_available(
            call_id,
            output,
            langchain_tool_call_id=current_lc_tool_call_id["value"],
        )

    def next_thinking_step_id() -> str:
        nonlocal thinking_step_counter
        thinking_step_counter += 1
        return f"{step_prefix}-{thinking_step_counter}"

    def complete_current_step() -> str | None:
        nonlocal last_active_step_id
        if last_active_step_id and last_active_step_id not in completed_step_ids:
            completed_step_ids.add(last_active_step_id)
            event = streaming_service.format_thinking_step(
                step_id=last_active_step_id,
                title=last_active_step_title,
                status="completed",
                items=last_active_step_items if last_active_step_items else None,
            )
            last_active_step_id = None
            return event
        return None

    async for event in agent.astream_events(input_data, config=config, version="v2"):
        event_type = event.get("event", "")

        if event_type == "on_chat_model_stream":
            if active_tool_depth > 0:
                continue  # Suppress inner-tool LLM tokens from leaking into chat
            if "surfsense:internal" in event.get("tags", []):
                continue  # Suppress middleware-internal LLM tokens (e.g. KB search classification)
            chunk = event.get("data", {}).get("chunk")
            if not chunk:
                continue
            parts = _extract_chunk_parts(chunk)

            reasoning_delta = parts["reasoning"]
            text_delta = parts["text"]

            # Reasoning streaming. Open a reasoning block on first
            # delta; append every subsequent delta until text begins.
            # When text starts we close the reasoning block first so the
            # frontend sees the natural hand-off. Gated behind the
            # parity-v2 flag so legacy deployments keep today's shape.
            if parity_v2 and reasoning_delta:
                if current_text_id is not None:
                    yield streaming_service.format_text_end(current_text_id)
                    current_text_id = None
                if current_reasoning_id is None:
                    completion_event = complete_current_step()
                    if completion_event:
                        yield completion_event
                    if just_finished_tool:
                        last_active_step_id = None
                        last_active_step_title = ""
                        last_active_step_items = []
                        just_finished_tool = False
                    current_reasoning_id = streaming_service.generate_reasoning_id()
                    yield streaming_service.format_reasoning_start(current_reasoning_id)
                yield streaming_service.format_reasoning_delta(
                    current_reasoning_id, reasoning_delta
                )

            if text_delta:
                if current_reasoning_id is not None:
                    yield streaming_service.format_reasoning_end(current_reasoning_id)
                    current_reasoning_id = None
                if current_text_id is None:
                    completion_event = complete_current_step()
                    if completion_event:
                        yield completion_event
                    if just_finished_tool:
                        last_active_step_id = None
                        last_active_step_title = ""
                        last_active_step_items = []
                        just_finished_tool = False
                    current_text_id = streaming_service.generate_text_id()
                    yield streaming_service.format_text_start(current_text_id)
                yield streaming_service.format_text_delta(current_text_id, text_delta)
                accumulated_text += text_delta

            # Live tool-call argument streaming. Runs AFTER text/reasoning
            # processing so chunks containing both stay in their natural
            # wire order (text → text-end → tool-input-start). Active
            # text/reasoning are closed inside the registration branch
            # before ``tool-input-start`` so the frontend sees a clean
            # part boundary even when providers interleave.
            if parity_v2 and parts["tool_call_chunks"]:
                for tcc in parts["tool_call_chunks"]:
                    idx = tcc.get("index")

                    # Register this index when we first see id+name
                    # TOGETHER. Per LangChain ToolCallChunk semantics the
                    # first chunk for a tool call carries both fields
                    # together; later chunks have id=None, name=None and
                    # only ``args``. Requiring BOTH keeps wire
                    # ``tool-input-start`` always carrying a real
                    # toolName (assistant-ui's typed tool-part dispatch
                    # keys off it).
                    if idx is not None and idx not in index_to_meta:
                        lc_id = tcc.get("id")
                        name = tcc.get("name")
                        if lc_id and name:
                            ui_id = lc_id

                            # Close active text/reasoning so wire
                            # ordering stays clean even on providers
                            # that interleave text and tool-call chunks
                            # within the same stream window.
                            if current_text_id is not None:
                                yield streaming_service.format_text_end(current_text_id)
                                current_text_id = None
                            if current_reasoning_id is not None:
                                yield streaming_service.format_reasoning_end(
                                    current_reasoning_id
                                )
                                current_reasoning_id = None

                            index_to_meta[idx] = {
                                "ui_id": ui_id,
                                "lc_id": lc_id,
                                "name": name,
                            }
                            yield streaming_service.format_tool_input_start(
                                ui_id,
                                name,
                                langchain_tool_call_id=lc_id,
                            )

                    # Emit args delta for any chunk at a registered
                    # index (including idless continuations). Once an
                    # index is owned by ``index_to_meta`` we DO NOT
                    # append to ``pending_tool_call_chunks`` — that list
                    # is reserved for the parity_v2-OFF / unmatched
                    # fallback path so it never re-pops chunks already
                    # consumed here (skip-append).
                    meta = index_to_meta.get(idx) if idx is not None else None
                    if meta:
                        args_chunk = tcc.get("args") or ""
                        if args_chunk:
                            yield streaming_service.format_tool_input_delta(
                                meta["ui_id"], args_chunk
                            )
                    else:
                        pending_tool_call_chunks.append(tcc)

        elif event_type == "on_tool_start":
            active_tool_depth += 1
            tool_name = event.get("name", "unknown_tool")
            run_id = event.get("run_id", "")
            tool_input = event.get("data", {}).get("input", {})
            if tool_name in ("write_file", "edit_file"):
                result.write_attempted = True

            if current_text_id is not None:
                yield streaming_service.format_text_end(current_text_id)
                current_text_id = None

            if last_active_step_title != "Synthesizing response":
                completion_event = complete_current_step()
                if completion_event:
                    yield completion_event

            just_finished_tool = False
            tool_step_id = next_thinking_step_id()
            tool_step_ids[run_id] = tool_step_id
            last_active_step_id = tool_step_id

            if tool_name == "ls":
                ls_path = (
                    tool_input.get("path", "/")
                    if isinstance(tool_input, dict)
                    else str(tool_input)
                )
                last_active_step_title = "Listing files"
                last_active_step_items = [ls_path]
                yield streaming_service.format_thinking_step(
                    step_id=tool_step_id,
                    title="Listing files",
                    status="in_progress",
                    items=last_active_step_items,
                )
            elif tool_name == "read_file":
                fp = (
                    tool_input.get("file_path", "")
                    if isinstance(tool_input, dict)
                    else str(tool_input)
                )
                display_fp = fp if len(fp) <= 80 else "…" + fp[-77:]
                last_active_step_title = "Reading file"
                last_active_step_items = [display_fp]
                yield streaming_service.format_thinking_step(
                    step_id=tool_step_id,
                    title="Reading file",
                    status="in_progress",
                    items=last_active_step_items,
                )
            elif tool_name == "write_file":
                fp = (
                    tool_input.get("file_path", "")
                    if isinstance(tool_input, dict)
                    else str(tool_input)
                )
                display_fp = fp if len(fp) <= 80 else "…" + fp[-77:]
                last_active_step_title = "Writing file"
                last_active_step_items = [display_fp]
                yield streaming_service.format_thinking_step(
                    step_id=tool_step_id,
                    title="Writing file",
                    status="in_progress",
                    items=last_active_step_items,
                )
            elif tool_name == "edit_file":
                fp = (
                    tool_input.get("file_path", "")
                    if isinstance(tool_input, dict)
                    else str(tool_input)
                )
                display_fp = fp if len(fp) <= 80 else "…" + fp[-77:]
                last_active_step_title = "Editing file"
                last_active_step_items = [display_fp]
                yield streaming_service.format_thinking_step(
                    step_id=tool_step_id,
                    title="Editing file",
                    status="in_progress",
                    items=last_active_step_items,
                )
            elif tool_name == "glob":
                pat = (
                    tool_input.get("pattern", "")
                    if isinstance(tool_input, dict)
                    else str(tool_input)
                )
                base_path = (
                    tool_input.get("path", "/") if isinstance(tool_input, dict) else "/"
                )
                last_active_step_title = "Searching files"
                last_active_step_items = [f"{pat} in {base_path}"]
                yield streaming_service.format_thinking_step(
                    step_id=tool_step_id,
                    title="Searching files",
                    status="in_progress",
                    items=last_active_step_items,
                )
            elif tool_name == "grep":
                pat = (
                    tool_input.get("pattern", "")
                    if isinstance(tool_input, dict)
                    else str(tool_input)
                )
                grep_path = (
                    tool_input.get("path", "") if isinstance(tool_input, dict) else ""
                )
                display_pat = pat[:60] + ("…" if len(pat) > 60 else "")
                last_active_step_title = "Searching content"
                last_active_step_items = [
                    f'"{display_pat}"' + (f" in {grep_path}" if grep_path else "")
                ]
                yield streaming_service.format_thinking_step(
                    step_id=tool_step_id,
                    title="Searching content",
                    status="in_progress",
                    items=last_active_step_items,
                )
            elif tool_name == "rm":
                rm_path = (
                    tool_input.get("path", "")
                    if isinstance(tool_input, dict)
                    else str(tool_input)
                )
                display_path = rm_path if len(rm_path) <= 80 else "…" + rm_path[-77:]
                last_active_step_title = "Deleting file"
                last_active_step_items = [display_path] if display_path else []
                yield streaming_service.format_thinking_step(
                    step_id=tool_step_id,
                    title="Deleting file",
                    status="in_progress",
                    items=last_active_step_items,
                )
            elif tool_name == "rmdir":
                rmdir_path = (
                    tool_input.get("path", "")
                    if isinstance(tool_input, dict)
                    else str(tool_input)
                )
                display_path = (
                    rmdir_path if len(rmdir_path) <= 80 else "…" + rmdir_path[-77:]
                )
                last_active_step_title = "Deleting folder"
                last_active_step_items = [display_path] if display_path else []
                yield streaming_service.format_thinking_step(
                    step_id=tool_step_id,
                    title="Deleting folder",
                    status="in_progress",
                    items=last_active_step_items,
                )
            elif tool_name == "mkdir":
                mkdir_path = (
                    tool_input.get("path", "")
                    if isinstance(tool_input, dict)
                    else str(tool_input)
                )
                display_path = (
                    mkdir_path if len(mkdir_path) <= 80 else "…" + mkdir_path[-77:]
                )
                last_active_step_title = "Creating folder"
                last_active_step_items = [display_path] if display_path else []
                yield streaming_service.format_thinking_step(
                    step_id=tool_step_id,
                    title="Creating folder",
                    status="in_progress",
                    items=last_active_step_items,
                )
            elif tool_name == "move_file":
                src = (
                    tool_input.get("source_path", "")
                    if isinstance(tool_input, dict)
                    else ""
                )
                dst = (
                    tool_input.get("destination_path", "")
                    if isinstance(tool_input, dict)
                    else ""
                )
                display_src = src if len(src) <= 60 else "…" + src[-57:]
                display_dst = dst if len(dst) <= 60 else "…" + dst[-57:]
                last_active_step_title = "Moving file"
                last_active_step_items = (
                    [f"{display_src} → {display_dst}"] if src or dst else []
                )
                yield streaming_service.format_thinking_step(
                    step_id=tool_step_id,
                    title="Moving file",
                    status="in_progress",
                    items=last_active_step_items,
                )
            elif tool_name == "write_todos":
                todos = (
                    tool_input.get("todos", []) if isinstance(tool_input, dict) else []
                )
                todo_count = len(todos) if isinstance(todos, list) else 0
                last_active_step_title = "Planning tasks"
                last_active_step_items = (
                    [f"{todo_count} task{'s' if todo_count != 1 else ''}"]
                    if todo_count
                    else []
                )
                yield streaming_service.format_thinking_step(
                    step_id=tool_step_id,
                    title="Planning tasks",
                    status="in_progress",
                    items=last_active_step_items,
                )
            elif tool_name == "save_document":
                doc_title = (
                    tool_input.get("title", "")
                    if isinstance(tool_input, dict)
                    else str(tool_input)
                )
                display_title = doc_title[:60] + ("…" if len(doc_title) > 60 else "")
                last_active_step_title = "Saving document"
                last_active_step_items = [display_title]
                yield streaming_service.format_thinking_step(
                    step_id=tool_step_id,
                    title="Saving document",
                    status="in_progress",
                    items=last_active_step_items,
                )
            elif tool_name == "generate_image":
                prompt = (
                    tool_input.get("prompt", "")
                    if isinstance(tool_input, dict)
                    else str(tool_input)
                )
                last_active_step_title = "Generating image"
                last_active_step_items = [
                    f"Prompt: {prompt[:80]}{'...' if len(prompt) > 80 else ''}"
                ]
                yield streaming_service.format_thinking_step(
                    step_id=tool_step_id,
                    title="Generating image",
                    status="in_progress",
                    items=last_active_step_items,
                )
            elif tool_name == "scrape_webpage":
                url = (
                    tool_input.get("url", "")
                    if isinstance(tool_input, dict)
                    else str(tool_input)
                )
                last_active_step_title = "Scraping webpage"
                last_active_step_items = [
                    f"URL: {url[:80]}{'...' if len(url) > 80 else ''}"
                ]
                yield streaming_service.format_thinking_step(
                    step_id=tool_step_id,
                    title="Scraping webpage",
                    status="in_progress",
                    items=last_active_step_items,
                )
            elif tool_name == "generate_podcast":
                podcast_title = (
                    tool_input.get("podcast_title", "SurfSense Podcast")
                    if isinstance(tool_input, dict)
                    else "SurfSense Podcast"
                )
                content_len = len(
                    tool_input.get("source_content", "")
                    if isinstance(tool_input, dict)
                    else ""
                )
                last_active_step_title = "Generating podcast"
                last_active_step_items = [
                    f"Title: {podcast_title}",
                    f"Content: {content_len:,} characters",
                    "Preparing audio generation...",
                ]
                yield streaming_service.format_thinking_step(
                    step_id=tool_step_id,
                    title="Generating podcast",
                    status="in_progress",
                    items=last_active_step_items,
                )
            elif tool_name == "generate_report":
                report_topic = (
                    tool_input.get("topic", "Report")
                    if isinstance(tool_input, dict)
                    else "Report"
                )
                is_revision = bool(
                    isinstance(tool_input, dict) and tool_input.get("parent_report_id")
                )
                step_title = "Revising report" if is_revision else "Generating report"
                last_active_step_title = step_title
                last_active_step_items = [
                    f"Topic: {report_topic}",
                    "Analyzing source content...",
                ]
                yield streaming_service.format_thinking_step(
                    step_id=tool_step_id,
                    title=step_title,
                    status="in_progress",
                    items=last_active_step_items,
                )
            elif tool_name in ("execute", "execute_code"):
                cmd = (
                    tool_input.get("command", "")
                    if isinstance(tool_input, dict)
                    else str(tool_input)
                )
                display_cmd = cmd[:80] + ("…" if len(cmd) > 80 else "")
                last_active_step_title = "Running command"
                last_active_step_items = [f"$ {display_cmd}"]
                yield streaming_service.format_thinking_step(
                    step_id=tool_step_id,
                    title="Running command",
                    status="in_progress",
                    items=last_active_step_items,
                )
            else:
                # Fallback for tools without a curated thinking-step title
                # (typically connector tools, MCP-registered tools, or
                # newly added tools that haven't been wired up here yet).
                # Render the snake_cased name as a sentence-cased phrase
                # so non-technical users see e.g. "Send gmail email"
                # rather than the raw identifier "send_gmail_email".
                last_active_step_title = (
                    tool_name.replace("_", " ").strip().capitalize() or tool_name
                )
                last_active_step_items = []
                yield streaming_service.format_thinking_step(
                    step_id=tool_step_id,
                    title=last_active_step_title,
                    status="in_progress",
                )

            # Resolve the card identity. If the chunk-emission loop
            # already registered an ``index`` for this tool call (parity_v2
            # path), reuse the same ui_id so the card sees:
            # tool-input-start → deltas… → tool-input-available →
            # tool-output-available all keyed by lc_id. Otherwise fall
            # back to the synthetic ``call_<run_id>`` id and the legacy
            # best-effort match against ``pending_tool_call_chunks``.
            matched_meta: dict[str, str] | None = None
            if parity_v2:
                # FIFO over indices 0,1,2…; first unassigned same-name
                # match wins. Handles parallel same-name calls (e.g. two
                # write_file calls) deterministically as long as the
                # model interleaves on_tool_start in the same order it
                # streamed the args.
                taken_ui_ids = set(ui_tool_call_id_by_run.values())
                for meta in index_to_meta.values():
                    if meta["name"] == tool_name and meta["ui_id"] not in taken_ui_ids:
                        matched_meta = meta
                        break

            tool_call_id: str
            langchain_tool_call_id: str | None = None
            if matched_meta is not None:
                tool_call_id = matched_meta["ui_id"]
                langchain_tool_call_id = matched_meta["lc_id"]
                # ``tool-input-start`` already fired during chunk
                # emission — skip the duplicate. No pruning is needed
                # because the chunk-emission loop intentionally never
                # appends registered-index chunks to
                # ``pending_tool_call_chunks`` (skip-append).
                if run_id:
                    lc_tool_call_id_by_run[run_id] = matched_meta["lc_id"]
            else:
                tool_call_id = (
                    f"call_{run_id[:32]}"
                    if run_id
                    else streaming_service.generate_tool_call_id()
                )
                # Legacy fallback: parity_v2 OFF, or parity_v2 ON but the
                # provider didn't stream tool_call_chunks for this call
                # (no index registered). Run the existing best-effort
                # match BEFORE emitting start so we still attach an
                # authoritative ``langchainToolCallId`` when possible.
                if parity_v2:
                    langchain_tool_call_id = _legacy_match_lc_id(
                        pending_tool_call_chunks,
                        tool_name,
                        run_id,
                        lc_tool_call_id_by_run,
                    )
                yield streaming_service.format_tool_input_start(
                    tool_call_id,
                    tool_name,
                    langchain_tool_call_id=langchain_tool_call_id,
                )

            if run_id:
                ui_tool_call_id_by_run[run_id] = tool_call_id

            # Sanitize tool_input: strip runtime-injected non-serializable
            # values (e.g. LangChain ToolRuntime) before sending over SSE.
            if isinstance(tool_input, dict):
                _safe_input: dict[str, Any] = {}
                for _k, _v in tool_input.items():
                    try:
                        json.dumps(_v)
                        _safe_input[_k] = _v
                    except (TypeError, ValueError, OverflowError):
                        pass
            else:
                _safe_input = {"input": tool_input}
            yield streaming_service.format_tool_input_available(
                tool_call_id,
                tool_name,
                _safe_input,
                langchain_tool_call_id=langchain_tool_call_id,
            )

        elif event_type == "on_tool_end":
            active_tool_depth = max(0, active_tool_depth - 1)
            run_id = event.get("run_id", "")
            tool_name = event.get("name", "unknown_tool")
            raw_output = event.get("data", {}).get("output", "")

            if tool_name == "update_memory":
                called_update_memory = True

            if hasattr(raw_output, "content"):
                content = raw_output.content
                if isinstance(content, str):
                    try:
                        tool_output = json.loads(content)
                    except (json.JSONDecodeError, TypeError):
                        tool_output = {"result": content}
                elif isinstance(content, dict):
                    tool_output = content
                else:
                    tool_output = {"result": str(content)}
            elif isinstance(raw_output, dict):
                tool_output = raw_output
            else:
                tool_output = {"result": str(raw_output) if raw_output else "completed"}

            if tool_name in ("write_file", "edit_file"):
                if _tool_output_has_error(tool_output):
                    # Keep successful evidence if a previous write/edit in this turn succeeded.
                    pass
                else:
                    result.write_succeeded = True
                    result.verification_succeeded = True

            # Look up the SAME card id used at on_tool_start (either the
            # parity_v2 lc-id-derived ui_id or the legacy synthetic
            # ``call_<run_id>``) so the output event always lands on the
            # same card as start/delta/available. Fallback preserves the
            # legacy synthetic shape for parity_v2-OFF / unknown-run paths.
            tool_call_id = ui_tool_call_id_by_run.get(
                run_id,
                f"call_{run_id[:32]}" if run_id else "call_unknown",
            )
            original_step_id = tool_step_ids.get(
                run_id, f"{step_prefix}-unknown-{run_id[:8]}"
            )
            completed_step_ids.add(original_step_id)

            # Authoritative LangChain tool_call_id from the returned
            # ``ToolMessage``. Falls back to whatever we matched
            # at ``on_tool_start`` time (kept in ``lc_tool_call_id_by_run``)
            # if the output isn't a ToolMessage. The value is stored in
            # ``current_lc_tool_call_id`` so ``_emit_tool_output``
            # picks it up for every output emit below.
            #
            # Emitted in BOTH parity_v2 and legacy modes: the chat tool
            # card needs the LangChain id to match against the
            # ``data-action-log`` SSE event (keyed by ``lc_tool_call_id``)
            # so the inline Revert button can light up. Reading
            # ``raw_output.tool_call_id`` is a cheap, non-mutating attribute
            # access that is safe regardless of feature-flag state.
            current_lc_tool_call_id["value"] = None
            authoritative = getattr(raw_output, "tool_call_id", None)
            if isinstance(authoritative, str) and authoritative:
                current_lc_tool_call_id["value"] = authoritative
                if run_id:
                    lc_tool_call_id_by_run[run_id] = authoritative
            elif run_id and run_id in lc_tool_call_id_by_run:
                current_lc_tool_call_id["value"] = lc_tool_call_id_by_run[run_id]

            if tool_name == "read_file":
                yield streaming_service.format_thinking_step(
                    step_id=original_step_id,
                    title="Reading file",
                    status="completed",
                    items=last_active_step_items,
                )
            elif tool_name == "write_file":
                yield streaming_service.format_thinking_step(
                    step_id=original_step_id,
                    title="Writing file",
                    status="completed",
                    items=last_active_step_items,
                )
            elif tool_name == "edit_file":
                yield streaming_service.format_thinking_step(
                    step_id=original_step_id,
                    title="Editing file",
                    status="completed",
                    items=last_active_step_items,
                )
            elif tool_name == "glob":
                yield streaming_service.format_thinking_step(
                    step_id=original_step_id,
                    title="Searching files",
                    status="completed",
                    items=last_active_step_items,
                )
            elif tool_name == "grep":
                yield streaming_service.format_thinking_step(
                    step_id=original_step_id,
                    title="Searching content",
                    status="completed",
                    items=last_active_step_items,
                )
            elif tool_name == "rm":
                yield streaming_service.format_thinking_step(
                    step_id=original_step_id,
                    title="Deleting file",
                    status="completed",
                    items=last_active_step_items,
                )
            elif tool_name == "rmdir":
                yield streaming_service.format_thinking_step(
                    step_id=original_step_id,
                    title="Deleting folder",
                    status="completed",
                    items=last_active_step_items,
                )
            elif tool_name == "mkdir":
                yield streaming_service.format_thinking_step(
                    step_id=original_step_id,
                    title="Creating folder",
                    status="completed",
                    items=last_active_step_items,
                )
            elif tool_name == "move_file":
                yield streaming_service.format_thinking_step(
                    step_id=original_step_id,
                    title="Moving file",
                    status="completed",
                    items=last_active_step_items,
                )
            elif tool_name == "write_todos":
                yield streaming_service.format_thinking_step(
                    step_id=original_step_id,
                    title="Planning tasks",
                    status="completed",
                    items=last_active_step_items,
                )
            elif tool_name == "save_document":
                result_str = (
                    tool_output.get("result", "")
                    if isinstance(tool_output, dict)
                    else str(tool_output)
                )
                is_error = "Error" in result_str
                completed_items = [
                    *last_active_step_items,
                    result_str[:80] if is_error else "Saved to knowledge base",
                ]
                yield streaming_service.format_thinking_step(
                    step_id=original_step_id,
                    title="Saving document",
                    status="completed",
                    items=completed_items,
                )
            elif tool_name == "generate_image":
                if isinstance(tool_output, dict) and not tool_output.get("error"):
                    completed_items = [
                        *last_active_step_items,
                        "Image generated successfully",
                    ]
                else:
                    error_msg = (
                        tool_output.get("error", "Generation failed")
                        if isinstance(tool_output, dict)
                        else "Generation failed"
                    )
                    completed_items = [*last_active_step_items, f"Error: {error_msg}"]
                yield streaming_service.format_thinking_step(
                    step_id=original_step_id,
                    title="Generating image",
                    status="completed",
                    items=completed_items,
                )
            elif tool_name == "scrape_webpage":
                if isinstance(tool_output, dict):
                    title = tool_output.get("title", "Webpage")
                    word_count = tool_output.get("word_count", 0)
                    has_error = "error" in tool_output
                    if has_error:
                        completed_items = [
                            *last_active_step_items,
                            f"Error: {tool_output.get('error', 'Failed to scrape')[:50]}",
                        ]
                    else:
                        completed_items = [
                            *last_active_step_items,
                            f"Title: {title[:50]}{'...' if len(title) > 50 else ''}",
                            f"Extracted: {word_count:,} words",
                        ]
                else:
                    completed_items = [*last_active_step_items, "Content extracted"]
                yield streaming_service.format_thinking_step(
                    step_id=original_step_id,
                    title="Scraping webpage",
                    status="completed",
                    items=completed_items,
                )
            elif tool_name == "generate_podcast":
                podcast_status = (
                    tool_output.get("status", "unknown")
                    if isinstance(tool_output, dict)
                    else "unknown"
                )
                podcast_title = (
                    tool_output.get("title", "Podcast")
                    if isinstance(tool_output, dict)
                    else "Podcast"
                )
                if podcast_status == "processing":
                    completed_items = [
                        f"Title: {podcast_title}",
                        "Audio generation started",
                        "Processing in background...",
                    ]
                elif podcast_status == "already_generating":
                    completed_items = [
                        f"Title: {podcast_title}",
                        "Podcast already in progress",
                        "Please wait for it to complete",
                    ]
                elif podcast_status == "error":
                    error_msg = (
                        tool_output.get("error", "Unknown error")
                        if isinstance(tool_output, dict)
                        else "Unknown error"
                    )
                    completed_items = [
                        f"Title: {podcast_title}",
                        f"Error: {error_msg[:50]}",
                    ]
                else:
                    completed_items = last_active_step_items
                yield streaming_service.format_thinking_step(
                    step_id=original_step_id,
                    title="Generating podcast",
                    status="completed",
                    items=completed_items,
                )
            elif tool_name == "generate_video_presentation":
                vp_status = (
                    tool_output.get("status", "unknown")
                    if isinstance(tool_output, dict)
                    else "unknown"
                )
                vp_title = (
                    tool_output.get("title", "Presentation")
                    if isinstance(tool_output, dict)
                    else "Presentation"
                )
                if vp_status in ("pending", "generating"):
                    completed_items = [
                        f"Title: {vp_title}",
                        "Presentation generation started",
                        "Processing in background...",
                    ]
                elif vp_status == "failed":
                    error_msg = (
                        tool_output.get("error", "Unknown error")
                        if isinstance(tool_output, dict)
                        else "Unknown error"
                    )
                    completed_items = [
                        f"Title: {vp_title}",
                        f"Error: {error_msg[:50]}",
                    ]
                else:
                    completed_items = last_active_step_items
                yield streaming_service.format_thinking_step(
                    step_id=original_step_id,
                    title="Generating video presentation",
                    status="completed",
                    items=completed_items,
                )
            elif tool_name == "generate_report":
                report_status = (
                    tool_output.get("status", "unknown")
                    if isinstance(tool_output, dict)
                    else "unknown"
                )
                report_title = (
                    tool_output.get("title", "Report")
                    if isinstance(tool_output, dict)
                    else "Report"
                )
                word_count = (
                    tool_output.get("word_count", 0)
                    if isinstance(tool_output, dict)
                    else 0
                )
                is_revision = (
                    tool_output.get("is_revision", False)
                    if isinstance(tool_output, dict)
                    else False
                )
                step_title = "Revising report" if is_revision else "Generating report"

                if report_status == "ready":
                    completed_items = [
                        f"Topic: {report_title}",
                        f"{word_count:,} words",
                        "Report ready",
                    ]
                elif report_status == "failed":
                    error_msg = (
                        tool_output.get("error", "Unknown error")
                        if isinstance(tool_output, dict)
                        else "Unknown error"
                    )
                    completed_items = [
                        f"Topic: {report_title}",
                        f"Error: {error_msg[:50]}",
                    ]
                else:
                    completed_items = last_active_step_items

                yield streaming_service.format_thinking_step(
                    step_id=original_step_id,
                    title=step_title,
                    status="completed",
                    items=completed_items,
                )
            elif tool_name in ("execute", "execute_code"):
                raw_text = (
                    tool_output.get("result", "")
                    if isinstance(tool_output, dict)
                    else str(tool_output)
                )
                m = re.match(r"^Exit code:\s*(\d+)", raw_text)
                exit_code_val = int(m.group(1)) if m else None
                if exit_code_val is not None and exit_code_val == 0:
                    completed_items = [
                        *last_active_step_items,
                        "Completed successfully",
                    ]
                elif exit_code_val is not None:
                    completed_items = [
                        *last_active_step_items,
                        f"Exit code: {exit_code_val}",
                    ]
                else:
                    completed_items = [*last_active_step_items, "Finished"]
                yield streaming_service.format_thinking_step(
                    step_id=original_step_id,
                    title="Running command",
                    status="completed",
                    items=completed_items,
                )
            elif tool_name == "ls":
                if isinstance(tool_output, dict):
                    ls_output = tool_output.get("result", "")
                elif isinstance(tool_output, str):
                    ls_output = tool_output
                else:
                    ls_output = str(tool_output) if tool_output else ""
                file_names: list[str] = []
                if ls_output:
                    paths: list[str] = []
                    try:
                        parsed = ast.literal_eval(ls_output)
                        if isinstance(parsed, list):
                            paths = [str(p) for p in parsed]
                    except (ValueError, SyntaxError):
                        paths = [
                            line.strip()
                            for line in ls_output.strip().split("\n")
                            if line.strip()
                        ]
                    for p in paths:
                        name = p.rstrip("/").split("/")[-1]
                        if name and len(name) <= 40:
                            file_names.append(name)
                        elif name:
                            file_names.append(name[:37] + "...")
                if file_names:
                    if len(file_names) <= 5:
                        completed_items = [f"[{name}]" for name in file_names]
                    else:
                        completed_items = [f"[{name}]" for name in file_names[:4]]
                        completed_items.append(f"(+{len(file_names) - 4} more)")
                else:
                    completed_items = ["No files found"]
                yield streaming_service.format_thinking_step(
                    step_id=original_step_id,
                    title="Listing files",
                    status="completed",
                    items=completed_items,
                )
            else:
                # Fallback completion title — see the matching in-progress
                # branch above for the wording rationale.
                fallback_title = (
                    tool_name.replace("_", " ").strip().capitalize() or tool_name
                )
                yield streaming_service.format_thinking_step(
                    step_id=original_step_id,
                    title=fallback_title,
                    status="completed",
                    items=last_active_step_items,
                )

            just_finished_tool = True
            last_active_step_id = None
            last_active_step_title = ""
            last_active_step_items = []

            if tool_name == "generate_podcast":
                yield _emit_tool_output(
                    tool_call_id,
                    tool_output
                    if isinstance(tool_output, dict)
                    else {"result": tool_output},
                )
                if (
                    isinstance(tool_output, dict)
                    and tool_output.get("status") == "success"
                ):
                    yield streaming_service.format_terminal_info(
                        f"Podcast generated successfully: {tool_output.get('title', 'Podcast')}",
                        "success",
                    )
                else:
                    error_msg = (
                        tool_output.get("error", "Unknown error")
                        if isinstance(tool_output, dict)
                        else "Unknown error"
                    )
                    yield streaming_service.format_terminal_info(
                        f"Podcast generation failed: {error_msg}",
                        "error",
                    )
            elif tool_name == "generate_video_presentation":
                yield _emit_tool_output(
                    tool_call_id,
                    tool_output
                    if isinstance(tool_output, dict)
                    else {"result": tool_output},
                )
                if (
                    isinstance(tool_output, dict)
                    and tool_output.get("status") == "pending"
                ):
                    yield streaming_service.format_terminal_info(
                        f"Video presentation queued: {tool_output.get('title', 'Presentation')}",
                        "success",
                    )
                elif (
                    isinstance(tool_output, dict)
                    and tool_output.get("status") == "failed"
                ):
                    error_msg = (
                        tool_output.get("error", "Unknown error")
                        if isinstance(tool_output, dict)
                        else "Unknown error"
                    )
                    yield streaming_service.format_terminal_info(
                        f"Presentation generation failed: {error_msg}",
                        "error",
                    )
            elif tool_name == "generate_image":
                yield _emit_tool_output(
                    tool_call_id,
                    tool_output
                    if isinstance(tool_output, dict)
                    else {"result": tool_output},
                )
                if isinstance(tool_output, dict):
                    if tool_output.get("error"):
                        yield streaming_service.format_terminal_info(
                            f"Image generation failed: {tool_output['error'][:60]}",
                            "error",
                        )
                    else:
                        yield streaming_service.format_terminal_info(
                            "Image generated successfully",
                            "success",
                        )
            elif tool_name == "scrape_webpage":
                if isinstance(tool_output, dict):
                    display_output = {
                        k: v for k, v in tool_output.items() if k != "content"
                    }
                    if "content" in tool_output:
                        content = tool_output.get("content", "")
                        display_output["content_preview"] = (
                            content[:500] + "..." if len(content) > 500 else content
                        )
                    yield _emit_tool_output(
                        tool_call_id,
                        display_output,
                    )
                else:
                    yield _emit_tool_output(
                        tool_call_id,
                        {"result": tool_output},
                    )
                if isinstance(tool_output, dict) and "error" not in tool_output:
                    title = tool_output.get("title", "Webpage")
                    word_count = tool_output.get("word_count", 0)
                    yield streaming_service.format_terminal_info(
                        f"Scraped: {title[:40]}{'...' if len(title) > 40 else ''} ({word_count:,} words)",
                        "success",
                    )
                else:
                    error_msg = (
                        tool_output.get("error", "Failed to scrape")
                        if isinstance(tool_output, dict)
                        else "Failed to scrape"
                    )
                    yield streaming_service.format_terminal_info(
                        f"Scrape failed: {error_msg}",
                        "error",
                    )
            elif tool_name in ("write_file", "edit_file"):
                resolved_path = _extract_resolved_file_path(
                    tool_name=tool_name,
                    tool_output=tool_output,
                )
                result_text = _tool_output_to_text(tool_output)
                if _tool_output_has_error(tool_output):
                    yield _emit_tool_output(
                        tool_call_id,
                        {
                            "status": "error",
                            "error": result_text,
                            "path": resolved_path,
                        },
                    )
                else:
                    yield _emit_tool_output(
                        tool_call_id,
                        {
                            "status": "completed",
                            "path": resolved_path,
                            "result": result_text,
                        },
                    )
            elif tool_name == "generate_report":
                # Stream the full report result so frontend can render the ReportCard
                yield _emit_tool_output(
                    tool_call_id,
                    tool_output
                    if isinstance(tool_output, dict)
                    else {"result": tool_output},
                )
                # Send appropriate terminal message based on status
                if (
                    isinstance(tool_output, dict)
                    and tool_output.get("status") == "ready"
                ):
                    word_count = tool_output.get("word_count", 0)
                    yield streaming_service.format_terminal_info(
                        f"Report generated: {tool_output.get('title', 'Report')} ({word_count:,} words)",
                        "success",
                    )
                else:
                    error_msg = (
                        tool_output.get("error", "Unknown error")
                        if isinstance(tool_output, dict)
                        else "Unknown error"
                    )
                    yield streaming_service.format_terminal_info(
                        f"Report generation failed: {error_msg}",
                        "error",
                    )
            elif tool_name == "generate_resume":
                yield _emit_tool_output(
                    tool_call_id,
                    tool_output
                    if isinstance(tool_output, dict)
                    else {"result": tool_output},
                )
                if (
                    isinstance(tool_output, dict)
                    and tool_output.get("status") == "ready"
                ):
                    yield streaming_service.format_terminal_info(
                        f"Resume generated: {tool_output.get('title', 'Resume')}",
                        "success",
                    )
                else:
                    error_msg = (
                        tool_output.get("error", "Unknown error")
                        if isinstance(tool_output, dict)
                        else "Unknown error"
                    )
                    yield streaming_service.format_terminal_info(
                        f"Resume generation failed: {error_msg}",
                        "error",
                    )
            elif tool_name in (
                "create_notion_page",
                "update_notion_page",
                "delete_notion_page",
                "create_linear_issue",
                "update_linear_issue",
                "delete_linear_issue",
                "create_google_drive_file",
                "delete_google_drive_file",
                "create_onedrive_file",
                "delete_onedrive_file",
                "create_dropbox_file",
                "delete_dropbox_file",
                "create_gmail_draft",
                "update_gmail_draft",
                "send_gmail_email",
                "trash_gmail_email",
                "create_calendar_event",
                "update_calendar_event",
                "delete_calendar_event",
                "create_jira_issue",
                "update_jira_issue",
                "delete_jira_issue",
                "create_confluence_page",
                "update_confluence_page",
                "delete_confluence_page",
            ):
                yield _emit_tool_output(
                    tool_call_id,
                    tool_output
                    if isinstance(tool_output, dict)
                    else {"result": tool_output},
                )
            elif tool_name in ("execute", "execute_code"):
                raw_text = (
                    tool_output.get("result", "")
                    if isinstance(tool_output, dict)
                    else str(tool_output)
                )
                exit_code: int | None = None
                output_text = raw_text
                m = re.match(r"^Exit code:\s*(\d+)", raw_text)
                if m:
                    exit_code = int(m.group(1))
                    om = re.search(r"\nOutput:\n([\s\S]*)", raw_text)
                    output_text = om.group(1) if om else ""
                thread_id_str = config.get("configurable", {}).get("thread_id", "")

                for sf_match in re.finditer(
                    r"^SANDBOX_FILE:\s*(.+)$", output_text, re.MULTILINE
                ):
                    fpath = sf_match.group(1).strip()
                    if fpath and fpath not in result.sandbox_files:
                        result.sandbox_files.append(fpath)

                yield _emit_tool_output(
                    tool_call_id,
                    {
                        "exit_code": exit_code,
                        "output": output_text,
                        "thread_id": thread_id_str,
                    },
                )
            elif tool_name == "web_search":
                xml = (
                    tool_output.get("result", str(tool_output))
                    if isinstance(tool_output, dict)
                    else str(tool_output)
                )
                citations: dict[str, dict[str, str]] = {}
                for m in re.finditer(
                    r"<title><!\[CDATA\[(.*?)\]\]></title>\s*<url><!\[CDATA\[(.*?)\]\]></url>",
                    xml,
                ):
                    title, url = m.group(1).strip(), m.group(2).strip()
                    if url.startswith("http") and url not in citations:
                        citations[url] = {"title": title}
                for m in re.finditer(
                    r"<chunk\s+id='([^']*)'><!\[CDATA\[([\s\S]*?)\]\]></chunk>",
                    xml,
                ):
                    chunk_url, content = m.group(1).strip(), m.group(2).strip()
                    if (
                        chunk_url.startswith("http")
                        and chunk_url in citations
                        and content
                    ):
                        citations[chunk_url]["snippet"] = (
                            content[:200] + "…" if len(content) > 200 else content
                        )
                yield _emit_tool_output(
                    tool_call_id,
                    {"status": "completed", "citations": citations},
                )
            else:
                yield _emit_tool_output(
                    tool_call_id,
                    {"status": "completed", "result_length": len(str(tool_output))},
                )
                yield streaming_service.format_terminal_info(
                    f"Tool {tool_name} completed", "success"
                )

        elif event_type == "on_custom_event" and event.get("name") == "report_progress":
            # Live progress updates from inside the generate_report tool
            data = event.get("data", {})
            message = data.get("message", "")
            if message and last_active_step_id:
                phase = data.get("phase", "")
                # Always keep the "Topic: ..." line
                topic_items = [
                    item for item in last_active_step_items if item.startswith("Topic:")
                ]

                if phase in ("revising_section", "adding_section"):
                    # During section-level ops: keep plan summary + show current op
                    plan_items = [
                        item
                        for item in last_active_step_items
                        if item.startswith("Topic:")
                        or item.startswith("Modifying ")
                        or item.startswith("Adding ")
                        or item.startswith("Removing ")
                    ]
                    # Only keep plan_items that don't end with "..." (not progress lines)
                    plan_items = [
                        item for item in plan_items if not item.endswith("...")
                    ]
                    last_active_step_items = [*plan_items, message]
                else:
                    # Phase transitions: replace everything after topic
                    last_active_step_items = [*topic_items, message]

                yield streaming_service.format_thinking_step(
                    step_id=last_active_step_id,
                    title=last_active_step_title,
                    status="in_progress",
                    items=last_active_step_items,
                )

        elif (
            event_type == "on_custom_event" and event.get("name") == "document_created"
        ):
            data = event.get("data", {})
            if data.get("id"):
                yield streaming_service.format_data(
                    "documents-updated",
                    {
                        "action": "created",
                        "document": data,
                    },
                )

        elif event_type == "on_custom_event" and event.get("name") == "action_log":
            # Surface a freshly committed AgentActionLog row so the chat
            # tool card can render its Revert button immediately.
            data = event.get("data", {})
            if data.get("id") is not None:
                yield streaming_service.format_data("action-log", data)

        elif (
            event_type == "on_custom_event"
            and event.get("name") == "action_log_updated"
        ):
            # Reversibility flipped in kb_persistence after the SAVEPOINT
            # for a destructive op (rm/rmdir/move/edit/write) committed.
            # Frontend uses this to flip the card's Revert
            # button on without re-fetching the actions list.
            data = event.get("data", {})
            if data.get("id") is not None:
                yield streaming_service.format_data("action-log-updated", data)

        elif event_type in ("on_chain_end", "on_agent_end"):
            if current_text_id is not None:
                yield streaming_service.format_text_end(current_text_id)
                current_text_id = None

    if current_text_id is not None:
        yield streaming_service.format_text_end(current_text_id)

    completion_event = complete_current_step()
    if completion_event:
        yield completion_event

    state = await agent.aget_state(config)
    state_values = getattr(state, "values", {}) or {}

    # Safety net: if astream_events was cancelled before
    # KnowledgeBasePersistenceMiddleware.aafter_agent ran, any staged work
    # (dirty_paths / staged_dirs / pending_moves / pending_deletes /
    # pending_dir_deletes) will still be in the checkpointed state. Run
    # the SAME shared commit helper here so the turn's writes don't get
    # lost on client disconnect, then push the delta back into the graph
    # using `as_node=...` so reducers fire as if the after_agent hook
    # produced it.
    if (
        fallback_commit_filesystem_mode == FilesystemMode.CLOUD
        and fallback_commit_search_space_id is not None
        and (
            (state_values.get("dirty_paths") or [])
            or (state_values.get("staged_dirs") or [])
            or (state_values.get("pending_moves") or [])
            or (state_values.get("pending_deletes") or [])
            or (state_values.get("pending_dir_deletes") or [])
        )
    ):
        try:
            delta = await commit_staged_filesystem_state(
                state_values,
                search_space_id=fallback_commit_search_space_id,
                created_by_id=fallback_commit_created_by_id,
                filesystem_mode=fallback_commit_filesystem_mode,
                thread_id=fallback_commit_thread_id,
                dispatch_events=False,
            )
            if delta:
                await agent.aupdate_state(
                    config,
                    delta,
                    as_node="KnowledgeBasePersistenceMiddleware.after_agent",
                )
        except Exception as exc:
            _perf_log.warning("[stream_new_chat] safety-net commit failed: %s", exc)

    contract_state = state_values.get("file_operation_contract") or {}
    contract_turn_id = contract_state.get("turn_id")
    current_turn_id = config.get("configurable", {}).get("turn_id", "")
    intent_value = contract_state.get("intent")
    if (
        isinstance(intent_value, str)
        and intent_value in ("chat_only", "file_write", "file_read")
        and contract_turn_id == current_turn_id
    ):
        result.intent_detected = intent_value
    if (
        isinstance(intent_value, str)
        and intent_value
        in (
            "chat_only",
            "file_write",
            "file_read",
        )
        and contract_turn_id != current_turn_id
    ):
        # Ignore stale intent contracts from previous turns/checkpoints.
        result.intent_detected = "chat_only"
    result.intent_confidence = (
        _safe_float(contract_state.get("confidence"), default=0.0)
        if contract_turn_id == current_turn_id
        else 0.0
    )

    if result.intent_detected == "file_write":
        result.commit_gate_passed, result.commit_gate_reason = (
            _evaluate_file_contract_outcome(result)
        )
        if not result.commit_gate_passed and _contract_enforcement_active(result):
            gate_notice = (
                "I could not complete the requested file write because no successful "
                "write_file/edit_file operation was confirmed."
            )
            gate_text_id = streaming_service.generate_text_id()
            yield streaming_service.format_text_start(gate_text_id)
            yield streaming_service.format_text_delta(gate_text_id, gate_notice)
            yield streaming_service.format_text_end(gate_text_id)
            yield streaming_service.format_terminal_info(gate_notice, "error")
            accumulated_text = gate_notice
    else:
        result.commit_gate_passed = True
        result.commit_gate_reason = ""

    result.accumulated_text = accumulated_text
    result.agent_called_update_memory = called_update_memory
    _log_file_contract("turn_outcome", result)

    is_interrupted = state.tasks and any(task.interrupts for task in state.tasks)
    if is_interrupted:
        result.is_interrupted = True
        result.interrupt_value = state.tasks[0].interrupts[0].value
        yield streaming_service.format_interrupt_request(result.interrupt_value)


async def stream_new_chat(
    user_query: str,
    search_space_id: int,
    chat_id: int,
    user_id: str | None = None,
    llm_config_id: int = -1,
    mentioned_document_ids: list[int] | None = None,
    mentioned_surfsense_doc_ids: list[int] | None = None,
    checkpoint_id: str | None = None,
    needs_history_bootstrap: bool = False,
    thread_visibility: ChatVisibility | None = None,
    current_user_display_name: str | None = None,
    disabled_tools: list[str] | None = None,
    filesystem_selection: FilesystemSelection | None = None,
    request_id: str | None = None,
    user_image_data_urls: list[str] | None = None,
    flow: Literal["new", "regenerate"] = "new",
) -> AsyncGenerator[str, None]:
    """
    Stream chat responses from the new SurfSense deep agent.

    This uses the Vercel AI SDK Data Stream Protocol (SSE format) for streaming.
    The chat_id is used as LangGraph's thread_id for memory/checkpointing.

    The function creates and manages its own database session to guarantee proper
    cleanup even when Starlette's middleware cancels the task on client disconnect.

    Args:
        user_query: The user's query
        search_space_id: The search space ID
        chat_id: The chat ID (used as LangGraph thread_id for memory)
        user_id: The current user's UUID string (for memory tools and session state)
        llm_config_id: The LLM configuration ID (default: -1 for first global config)
        needs_history_bootstrap: If True, load message history from DB (for cloned chats)
        mentioned_document_ids: Optional list of document IDs mentioned with @ in the chat
        mentioned_surfsense_doc_ids: Optional list of SurfSense doc IDs mentioned with @ in the chat
        checkpoint_id: Optional checkpoint ID to rewind/fork from (for edit/reload operations)

    Yields:
        str: SSE formatted response strings
    """
    streaming_service = VercelStreamingService()
    stream_result = StreamResult()
    _t_total = time.perf_counter()
    fs_mode = filesystem_selection.mode.value if filesystem_selection else "cloud"
    fs_platform = (
        filesystem_selection.client_platform.value if filesystem_selection else "web"
    )
    stream_result.request_id = request_id
    stream_result.turn_id = f"{chat_id}:{int(time.time() * 1000)}"
    stream_result.filesystem_mode = fs_mode
    stream_result.client_platform = fs_platform
    _log_file_contract("turn_start", stream_result)
    _perf_log.info(
        "[stream_new_chat] filesystem_mode=%s client_platform=%s",
        fs_mode,
        fs_platform,
    )
    log_system_snapshot("stream_new_chat_START")

    from app.services.token_tracking_service import start_turn

    accumulator = start_turn()

    # Premium quota tracking state
    _premium_reserved = 0
    _premium_request_id: str | None = None

    _emit_stream_error = partial(
        _emit_stream_terminal_error,
        streaming_service=streaming_service,
        flow=flow,
        request_id=request_id,
        thread_id=chat_id,
        search_space_id=search_space_id,
        user_id=user_id,
    )

    session = async_session_maker()
    try:
        # Mark AI as responding to this user for live collaboration
        if user_id:
            await set_ai_responding(session, chat_id, UUID(user_id))
        # Load LLM config - supports both YAML (negative IDs) and database (positive IDs)
        agent_config: AgentConfig | None = None
        requested_llm_config_id = llm_config_id

        async def _load_llm_bundle(
            config_id: int,
        ) -> tuple[Any, AgentConfig | None, str | None]:
            if config_id >= 0:
                loaded_agent_config = await load_agent_config(
                    session=session,
                    config_id=config_id,
                    search_space_id=search_space_id,
                )
                if not loaded_agent_config:
                    return (
                        None,
                        None,
                        f"Failed to load NewLLMConfig with id {config_id}",
                    )
                return (
                    create_chat_litellm_from_agent_config(loaded_agent_config),
                    loaded_agent_config,
                    None,
                )

            loaded_llm_config = load_global_llm_config_by_id(config_id)
            if not loaded_llm_config:
                return None, None, f"Failed to load LLM config with id {config_id}"
            return (
                create_chat_litellm_from_config(loaded_llm_config),
                AgentConfig.from_yaml_config(loaded_llm_config),
                None,
            )

        _t0 = time.perf_counter()
        try:
            llm_config_id = (
                await resolve_or_get_pinned_llm_config_id(
                    session,
                    thread_id=chat_id,
                    search_space_id=search_space_id,
                    user_id=user_id,
                    selected_llm_config_id=llm_config_id,
                )
            ).resolved_llm_config_id
        except ValueError as pin_error:
            yield _emit_stream_error(
                message=str(pin_error),
                error_kind="server_error",
                error_code="SERVER_ERROR",
            )
            yield streaming_service.format_done()
            return

        llm, agent_config, llm_load_error = await _load_llm_bundle(llm_config_id)
        if llm_load_error:
            yield _emit_stream_error(
                message=llm_load_error,
                error_kind="server_error",
                error_code="SERVER_ERROR",
            )
            yield streaming_service.format_done()
            return
        _perf_log.info(
            "[stream_new_chat] LLM config loaded in %.3fs (config_id=%s)",
            time.perf_counter() - _t0,
            llm_config_id,
        )

        # Premium quota reservation for pinned premium model only.
        _needs_premium_quota = (
            agent_config is not None and user_id and agent_config.is_premium
        )
        if _needs_premium_quota:
            import uuid as _uuid

            from app.config import config as _app_config
            from app.services.token_quota_service import TokenQuotaService

            _premium_request_id = _uuid.uuid4().hex[:16]
            reserve_amount = min(
                agent_config.quota_reserve_tokens
                or _app_config.QUOTA_MAX_RESERVE_PER_CALL,
                _app_config.QUOTA_MAX_RESERVE_PER_CALL,
            )
            async with shielded_async_session() as quota_session:
                quota_result = await TokenQuotaService.premium_reserve(
                    db_session=quota_session,
                    user_id=UUID(user_id),
                    request_id=_premium_request_id,
                    reserve_tokens=reserve_amount,
                )
            _premium_reserved = reserve_amount
            if not quota_result.allowed:
                if requested_llm_config_id == 0:
                    try:
                        llm_config_id = (
                            await resolve_or_get_pinned_llm_config_id(
                                session,
                                thread_id=chat_id,
                                search_space_id=search_space_id,
                                user_id=user_id,
                                selected_llm_config_id=0,
                                force_repin_free=True,
                            )
                        ).resolved_llm_config_id
                    except ValueError as pin_error:
                        yield _emit_stream_error(
                            message=str(pin_error),
                            error_kind="server_error",
                            error_code="SERVER_ERROR",
                        )
                        yield streaming_service.format_done()
                        return

                    llm, agent_config, llm_load_error = await _load_llm_bundle(
                        llm_config_id
                    )
                    if llm_load_error:
                        yield _emit_stream_error(
                            message=llm_load_error,
                            error_kind="server_error",
                            error_code="SERVER_ERROR",
                        )
                        yield streaming_service.format_done()
                        return
                    _premium_request_id = None
                    _premium_reserved = 0
                    _log_chat_stream_error(
                        flow=flow,
                        error_kind="premium_quota_exhausted",
                        error_code="PREMIUM_QUOTA_EXHAUSTED",
                        severity="info",
                        is_expected=True,
                        request_id=request_id,
                        thread_id=chat_id,
                        search_space_id=search_space_id,
                        user_id=user_id,
                        message=(
                            "Premium quota exhausted on pinned model; auto-fallback switched to a free model"
                        ),
                        extra={
                            "fallback_config_id": llm_config_id,
                            "auto_fallback": True,
                        },
                    )
                else:
                    yield _emit_stream_error(
                        message=(
                            "Buy more tokens to continue with this model, or switch to a free model"
                        ),
                        error_kind="premium_quota_exhausted",
                        error_code="PREMIUM_QUOTA_EXHAUSTED",
                        severity="info",
                        is_expected=True,
                        extra={
                            "resolved_config_id": llm_config_id,
                            "auto_fallback": False,
                        },
                    )
                    yield streaming_service.format_done()
                    return

        if not llm:
            yield _emit_stream_error(
                message="Failed to create LLM instance",
                error_kind="server_error",
                error_code="SERVER_ERROR",
            )
            yield streaming_service.format_done()
            return

        # Create connector service
        _t0 = time.perf_counter()
        connector_service = ConnectorService(session, search_space_id=search_space_id)

        firecrawl_api_key = None
        webcrawler_connector = await connector_service.get_connector_by_type(
            SearchSourceConnectorType.WEBCRAWLER_CONNECTOR, search_space_id
        )
        if webcrawler_connector and webcrawler_connector.config:
            firecrawl_api_key = webcrawler_connector.config.get("FIRECRAWL_API_KEY")
        _perf_log.info(
            "[stream_new_chat] Connector service + firecrawl key in %.3fs",
            time.perf_counter() - _t0,
        )

        # Get the PostgreSQL checkpointer for persistent conversation memory
        _t0 = time.perf_counter()
        checkpointer = await get_checkpointer()
        _perf_log.info(
            "[stream_new_chat] Checkpointer ready in %.3fs", time.perf_counter() - _t0
        )

        visibility = thread_visibility or ChatVisibility.PRIVATE
        _t0 = time.perf_counter()
        agent = await create_surfsense_deep_agent(
            llm=llm,
            search_space_id=search_space_id,
            db_session=session,
            connector_service=connector_service,
            checkpointer=checkpointer,
            user_id=user_id,
            thread_id=chat_id,
            agent_config=agent_config,
            firecrawl_api_key=firecrawl_api_key,
            thread_visibility=visibility,
            disabled_tools=disabled_tools,
            mentioned_document_ids=mentioned_document_ids,
            filesystem_selection=filesystem_selection,
        )
        _perf_log.info(
            "[stream_new_chat] Agent created in %.3fs", time.perf_counter() - _t0
        )

        # Build input with message history
        langchain_messages = []

        _t0 = time.perf_counter()
        # Bootstrap history for cloned chats (no LangGraph checkpoint exists yet)
        if needs_history_bootstrap:
            langchain_messages = await bootstrap_history_from_db(
                session, chat_id, thread_visibility=visibility
            )

            thread_result = await session.execute(
                select(NewChatThread).filter(NewChatThread.id == chat_id)
            )
            thread = thread_result.scalars().first()
            if thread:
                thread.needs_history_bootstrap = False
                await session.commit()

        # Mentioned KB documents are now handled by KnowledgeBaseSearchMiddleware
        # which merges them into the scoped filesystem with full document
        # structure. Only SurfSense docs and report context are inlined here.

        # Fetch mentioned SurfSense docs if any
        mentioned_surfsense_docs: list[SurfsenseDocsDocument] = []
        if mentioned_surfsense_doc_ids:
            result = await session.execute(
                select(SurfsenseDocsDocument)
                .options(selectinload(SurfsenseDocsDocument.chunks))
                .filter(
                    SurfsenseDocsDocument.id.in_(mentioned_surfsense_doc_ids),
                )
            )
            mentioned_surfsense_docs = list(result.scalars().all())

        # Fetch the most recent report(s) in this thread so the LLM can
        # easily find report_id for versioning decisions, instead of
        # having to dig through conversation history.
        recent_reports_result = await session.execute(
            select(Report)
            .filter(
                Report.thread_id == chat_id,
                Report.content.isnot(None),  # exclude failed reports
            )
            .order_by(Report.id.desc())
            .limit(3)
        )
        recent_reports = list(recent_reports_result.scalars().all())

        # Format the user query with context (SurfSense docs + reports only)
        final_query = user_query
        context_parts = []

        if mentioned_surfsense_docs:
            context_parts.append(
                format_mentioned_surfsense_docs_as_context(mentioned_surfsense_docs)
            )

        # Surface report IDs prominently so the LLM doesn't have to
        # retrieve them from old tool responses in conversation history.
        if recent_reports:
            report_lines = []
            for r in recent_reports:
                report_lines.append(
                    f'  - report_id={r.id}, title="{r.title}", '
                    f'style="{r.report_style or "detailed"}"'
                )
            reports_listing = "\n".join(report_lines)
            context_parts.append(
                "<report_context>\n"
                "Previously generated reports in this conversation:\n"
                f"{reports_listing}\n\n"
                "If the user wants to MODIFY, REVISE, UPDATE, or ADD to one of "
                "these reports, set parent_report_id to the relevant report_id above.\n"
                "If the user wants a completely NEW report on a different topic, "
                "leave parent_report_id unset.\n"
                "</report_context>"
            )

        if context_parts:
            context = "\n\n".join(context_parts)
            final_query = f"{context}\n\n<user_query>{user_query}</user_query>"

        if visibility == ChatVisibility.SEARCH_SPACE and current_user_display_name:
            final_query = f"**[{current_user_display_name}]:** {final_query}"

        # if messages:
        #     # Convert frontend messages to LangChain format
        #     for msg in messages:
        #         if msg.role == "user":
        #             langchain_messages.append(HumanMessage(content=msg.content))
        #         elif msg.role == "assistant":
        #             langchain_messages.append(AIMessage(content=msg.content))
        # else:
        human_content = build_human_message_content(
            final_query, list(user_image_data_urls or ())
        )
        langchain_messages.append(HumanMessage(content=human_content))

        input_state = {
            # Lets not pass this message atm because we are using the checkpointer to manage the conversation history
            # We will use this to simulate group chat functionality in the future
            "messages": langchain_messages,
            "search_space_id": search_space_id,
            "request_id": request_id or "unknown",
            "turn_id": stream_result.turn_id,
        }

        _perf_log.info(
            "[stream_new_chat] History bootstrap + doc/report queries in %.3fs",
            time.perf_counter() - _t0,
        )

        # All pre-streaming DB reads are done.  Commit to release the
        # transaction and its ACCESS SHARE locks so we don't block DDL
        # (e.g. migrations) for the entire duration of LLM streaming.
        # Tools that need DB access during streaming will start their own
        # short-lived transactions (or use isolated sessions).
        await session.commit()

        # Detach heavy ORM objects (documents with chunks, reports, etc.)
        # from the session identity map now that we've extracted the data
        # we need.  This prevents them from accumulating in memory for the
        # entire duration of LLM streaming (which can be several minutes).
        session.expunge_all()

        _perf_log.info(
            "[stream_new_chat] Total pre-stream setup in %.3fs (chat_id=%s)",
            time.perf_counter() - _t_total,
            chat_id,
        )

        # Configure LangGraph with thread_id for memory
        # If checkpoint_id is provided, fork from that checkpoint (for edit/reload)
        configurable = {"thread_id": str(chat_id)}
        configurable["request_id"] = request_id or "unknown"
        configurable["turn_id"] = stream_result.turn_id
        if checkpoint_id:
            configurable["checkpoint_id"] = checkpoint_id

        config = {
            "configurable": configurable,
            # Effectively uncapped, matching the agent-level
            # ``with_config`` default in ``chat_deepagent.create_agent``
            # and the unbounded ``while(true)`` loop used by OpenCode's
            # ``session/processor.ts``. Real circuit-breakers live in
            # middleware: ``DoomLoopMiddleware`` (sliding-window tool
            # signature check), plus ``enable_tool_call_limit`` /
            # ``enable_model_call_limit`` when those flags are set. The
            # original LangGraph default of 25 (and our previous 80
            # bump) hit users on legitimate multi-tool plans.
            "recursion_limit": 10_000,
        }

        # Start the message stream
        yield streaming_service.format_message_start()
        yield streaming_service.format_start_step()

        # Surface the per-turn correlation id at the very start of the
        # stream so the frontend can stamp it onto the in-flight
        # assistant message and replay it via ``appendMessage``
        # for durable storage. Tool/action-log events DO carry it later,
        # but pure-text turns never produce action-log events; this
        # event guarantees the frontend learns the turn id regardless.
        yield streaming_service.format_data(
            "turn-info",
            {"chat_turn_id": stream_result.turn_id},
        )
        yield streaming_service.format_data("turn-status", {"status": "busy"})

        # Initial thinking step - analyzing the request
        if mentioned_surfsense_docs:
            initial_title = "Analyzing referenced content"
            action_verb = "Analyzing"
        else:
            initial_title = "Understanding your request"
            action_verb = "Processing"

        processing_parts = []
        if user_query.strip():
            query_text = user_query[:80] + ("..." if len(user_query) > 80 else "")
            processing_parts.append(query_text)
        elif user_image_data_urls:
            processing_parts.append(f"[{len(user_image_data_urls)} image(s)]")
        else:
            processing_parts.append("(message)")

        if mentioned_surfsense_docs:
            doc_names = []
            for doc in mentioned_surfsense_docs:
                title = doc.title
                if len(title) > 30:
                    title = title[:27] + "..."
                doc_names.append(title)
            if len(doc_names) == 1:
                processing_parts.append(f"[{doc_names[0]}]")
            else:
                processing_parts.append(f"[{len(doc_names)} docs]")

        initial_items = [f"{action_verb}: {' '.join(processing_parts)}"]
        initial_step_id = "thinking-1"

        yield streaming_service.format_thinking_step(
            step_id=initial_step_id,
            title=initial_title,
            status="in_progress",
            items=initial_items,
        )

        # These ORM objects (with eagerly-loaded chunks) can be very large.
        # They're only needed to build context strings already copied into
        # final_query / langchain_messages — release them before streaming.
        del mentioned_surfsense_docs, recent_reports
        del langchain_messages, final_query

        # Check if this is the first assistant response so we can generate
        # a title in parallel with the agent stream (better UX than waiting
        # until after the full response).
        assistant_count_result = await session.execute(
            select(func.count(NewChatMessage.id)).filter(
                NewChatMessage.thread_id == chat_id,
                NewChatMessage.role == "assistant",
            )
        )
        is_first_response = (assistant_count_result.scalar() or 0) == 0

        title_task: asyncio.Task[tuple[str | None, dict | None]] | None = None
        if is_first_response:

            async def _generate_title() -> tuple[str | None, dict | None]:
                """Generate a short title via litellm.acompletion.

                Returns (title, usage_dict).  Usage is extracted directly from
                the response object because litellm fires its async callback
                via fire-and-forget ``create_task``, so the
                ``TokenTrackingCallback`` would run too late.  We also blank
                the accumulator in this child-task context so the late callback
                doesn't double-count.
                """
                try:
                    from litellm import acompletion

                    from app.services.llm_router_service import LLMRouterService
                    from app.services.token_tracking_service import _turn_accumulator

                    _turn_accumulator.set(None)

                    title_seed = user_query.strip() or (
                        f"[{len(user_image_data_urls or [])} image(s)]"
                        if user_image_data_urls
                        else ""
                    )
                    prompt = TITLE_GENERATION_PROMPT.replace(
                        "{user_query}", title_seed[:500] or "(message)"
                    )
                    messages = [{"role": "user", "content": prompt}]

                    if getattr(llm, "model", None) == "auto":
                        router = LLMRouterService.get_router()
                        response = await router.acompletion(
                            model="auto", messages=messages
                        )
                    else:
                        response = await acompletion(
                            model=llm.model,
                            messages=messages,
                            api_key=getattr(llm, "api_key", None),
                            api_base=getattr(llm, "api_base", None),
                        )

                    usage_info = None
                    usage = getattr(response, "usage", None)
                    if usage:
                        raw_model = getattr(llm, "model", "") or ""
                        model_name = (
                            raw_model.split("/", 1)[-1]
                            if "/" in raw_model
                            else (raw_model or response.model or "unknown")
                        )
                        usage_info = {
                            "model": model_name,
                            "prompt_tokens": getattr(usage, "prompt_tokens", 0) or 0,
                            "completion_tokens": getattr(usage, "completion_tokens", 0)
                            or 0,
                            "total_tokens": getattr(usage, "total_tokens", 0) or 0,
                        }

                    raw_title = response.choices[0].message.content.strip()
                    if raw_title and len(raw_title) <= 100:
                        return raw_title.strip("\"'"), usage_info
                    return None, usage_info
                except Exception:
                    logging.getLogger(__name__).exception(
                        "[TitleGen] _generate_title failed"
                    )
                    return None, None

            title_task = asyncio.create_task(_generate_title())

        title_emitted = False

        _t_stream_start = time.perf_counter()
        _first_event_logged = False
        runtime_rate_limit_recovered = False
        while True:
            try:
                async for sse in _stream_agent_events(
                    agent=agent,
                    config=config,
                    input_data=input_state,
                    streaming_service=streaming_service,
                    result=stream_result,
                    step_prefix="thinking",
                    initial_step_id=initial_step_id,
                    initial_step_title=initial_title,
                    initial_step_items=initial_items,
                    fallback_commit_search_space_id=search_space_id,
                    fallback_commit_created_by_id=user_id,
                    fallback_commit_filesystem_mode=(
                        filesystem_selection.mode
                        if filesystem_selection
                        else FilesystemMode.CLOUD
                    ),
                    fallback_commit_thread_id=chat_id,
                ):
                    if not _first_event_logged:
                        _perf_log.info(
                            "[stream_new_chat] First agent event in %.3fs (time since stream start), "
                            "%.3fs (total since request start) (chat_id=%s)",
                            time.perf_counter() - _t_stream_start,
                            time.perf_counter() - _t_total,
                            chat_id,
                        )
                        _first_event_logged = True
                    yield sse

                    # Inject title update mid-stream as soon as the background
                    # task finishes.
                    if title_task is not None and title_task.done() and not title_emitted:
                        generated_title, title_usage = title_task.result()
                        if title_usage:
                            accumulator.add(**title_usage)
                        if generated_title:
                            async with shielded_async_session() as title_session:
                                title_thread_result = await title_session.execute(
                                    select(NewChatThread).filter(
                                        NewChatThread.id == chat_id
                                    )
                                )
                                title_thread = title_thread_result.scalars().first()
                                if title_thread:
                                    title_thread.title = generated_title
                                    await title_session.commit()
                            yield streaming_service.format_thread_title_update(
                                chat_id, generated_title
                            )
                        title_emitted = True
                break
            except Exception as stream_exc:
                can_runtime_recover = (
                    not runtime_rate_limit_recovered
                    and requested_llm_config_id == 0
                    and llm_config_id < 0
                    and not _first_event_logged
                    and _is_provider_rate_limited(stream_exc)
                )
                if not can_runtime_recover:
                    raise

                runtime_rate_limit_recovered = True
                previous_config_id = llm_config_id
                # The failed attempt may still hold the per-thread busy mutex
                # (middleware teardown can lag behind raised provider errors).
                # Force release before we retry within the same request.
                end_turn(str(chat_id))
                mark_runtime_cooldown(
                    previous_config_id,
                    reason="provider_rate_limited",
                )

                llm_config_id = (
                    await resolve_or_get_pinned_llm_config_id(
                        session,
                        thread_id=chat_id,
                        search_space_id=search_space_id,
                        user_id=user_id,
                        selected_llm_config_id=0,
                        exclude_config_ids={previous_config_id},
                    )
                ).resolved_llm_config_id

                llm, agent_config, llm_load_error = await _load_llm_bundle(llm_config_id)
                if llm_load_error:
                    raise stream_exc

                # Title generation uses the initial llm object. After a runtime
                # repin we keep the stream focused on response recovery and skip
                # title generation for this turn.
                if title_task is not None and not title_task.done():
                    title_task.cancel()
                title_task = None

                _t0 = time.perf_counter()
                agent = await create_surfsense_deep_agent(
                    llm=llm,
                    search_space_id=search_space_id,
                    db_session=session,
                    connector_service=connector_service,
                    checkpointer=checkpointer,
                    user_id=user_id,
                    thread_id=chat_id,
                    agent_config=agent_config,
                    firecrawl_api_key=firecrawl_api_key,
                    thread_visibility=visibility,
                    disabled_tools=disabled_tools,
                    mentioned_document_ids=mentioned_document_ids,
                    filesystem_selection=filesystem_selection,
                )
                _perf_log.info(
                    "[stream_new_chat] Runtime rate-limit recovery repinned "
                    "config_id=%s -> %s and rebuilt agent in %.3fs",
                    previous_config_id,
                    llm_config_id,
                    time.perf_counter() - _t0,
                )
                _log_chat_stream_error(
                    flow=flow,
                    error_kind="rate_limited",
                    error_code="RATE_LIMITED",
                    severity="info",
                    is_expected=True,
                    request_id=request_id,
                    thread_id=chat_id,
                    search_space_id=search_space_id,
                    user_id=user_id,
                    message=(
                        "Auto-pinned model hit runtime rate limit; switched to "
                        "another eligible model and retried."
                    ),
                    extra={
                        "auto_runtime_recover": True,
                        "previous_config_id": previous_config_id,
                        "fallback_config_id": llm_config_id,
                    },
                )
                continue

        _perf_log.info(
            "[stream_new_chat] Agent stream completed in %.3fs (chat_id=%s)",
            time.perf_counter() - _t_stream_start,
            chat_id,
        )
        log_system_snapshot("stream_new_chat_END")

        if stream_result.is_interrupted:
            if title_task is not None and not title_task.done():
                title_task.cancel()

            usage_summary = accumulator.per_message_summary()
            _perf_log.info(
                "[token_usage] interrupted new_chat: calls=%d total=%d summary=%s",
                len(accumulator.calls),
                accumulator.grand_total,
                usage_summary,
            )
            if usage_summary:
                yield streaming_service.format_data(
                    "token-usage",
                    {
                        "usage": usage_summary,
                        "prompt_tokens": accumulator.total_prompt_tokens,
                        "completion_tokens": accumulator.total_completion_tokens,
                        "total_tokens": accumulator.grand_total,
                        "call_details": accumulator.serialized_calls(),
                    },
                )

            yield streaming_service.format_finish_step()
            yield streaming_service.format_finish()
            yield streaming_service.format_done()
            return

        # If the title task didn't finish during streaming, await it now
        if title_task is not None and not title_emitted:
            generated_title, title_usage = await title_task
            if title_usage:
                accumulator.add(**title_usage)
            if generated_title:
                async with shielded_async_session() as title_session:
                    title_thread_result = await title_session.execute(
                        select(NewChatThread).filter(NewChatThread.id == chat_id)
                    )
                    title_thread = title_thread_result.scalars().first()
                    if title_thread:
                        title_thread.title = generated_title
                        await title_session.commit()
                yield streaming_service.format_thread_title_update(
                    chat_id, generated_title
                )

        # Finalize premium quota with actual tokens.
        if _premium_request_id and user_id:
            try:
                from app.services.token_quota_service import TokenQuotaService

                async with shielded_async_session() as quota_session:
                    await TokenQuotaService.premium_finalize(
                        db_session=quota_session,
                        user_id=UUID(user_id),
                        request_id=_premium_request_id,
                        actual_tokens=accumulator.grand_total,
                        reserved_tokens=_premium_reserved,
                    )
                _premium_request_id = None
                _premium_reserved = 0
            except Exception:
                logging.getLogger(__name__).warning(
                    "Failed to finalize premium quota for user %s",
                    user_id,
                    exc_info=True,
                )

        usage_summary = accumulator.per_message_summary()
        _perf_log.info(
            "[token_usage] normal new_chat: calls=%d total=%d summary=%s",
            len(accumulator.calls),
            accumulator.grand_total,
            usage_summary,
        )
        if usage_summary:
            yield streaming_service.format_data(
                "token-usage",
                {
                    "usage": usage_summary,
                    "prompt_tokens": accumulator.total_prompt_tokens,
                    "completion_tokens": accumulator.total_completion_tokens,
                    "total_tokens": accumulator.grand_total,
                    "call_details": accumulator.serialized_calls(),
                },
            )

        # Fire background memory extraction if the agent didn't handle it.
        # Shared threads write to team memory; private threads write to user memory.
        if not stream_result.agent_called_update_memory:
            memory_seed = user_query.strip() or (
                f"[{len(user_image_data_urls or [])} image(s)]"
                if user_image_data_urls
                else "(message)"
            )
            if visibility == ChatVisibility.SEARCH_SPACE:
                task = asyncio.create_task(
                    extract_and_save_team_memory(
                        user_message=memory_seed,
                        search_space_id=search_space_id,
                        llm=llm,
                        author_display_name=current_user_display_name,
                    )
                )
                _background_tasks.add(task)
                task.add_done_callback(_background_tasks.discard)
            elif user_id:
                task = asyncio.create_task(
                    extract_and_save_memory(
                        user_message=memory_seed,
                        user_id=user_id,
                        llm=llm,
                    )
                )
                _background_tasks.add(task)
                task.add_done_callback(_background_tasks.discard)

        # Finish the step and message
        yield streaming_service.format_data("turn-status", {"status": "idle"})
        yield streaming_service.format_finish_step()
        yield streaming_service.format_finish()
        yield streaming_service.format_done()

    except Exception as e:
        # Handle any errors
        import traceback

        (
            error_kind,
            error_code,
            severity,
            is_expected,
            user_message,
            error_extra,
        ) = _classify_stream_exception(e, flow_label="chat")
        error_message = f"Error during chat: {e!s}"
        print(f"[stream_new_chat] {error_message}")
        print(f"[stream_new_chat] Exception type: {type(e).__name__}")
        print(f"[stream_new_chat] Traceback:\n{traceback.format_exc()}")
        if error_code == "TURN_CANCELLING":
            status_payload: dict[str, Any] = {"status": "cancelling"}
            if error_extra:
                status_payload.update(error_extra)
            yield streaming_service.format_data("turn-status", status_payload)
        else:
            yield streaming_service.format_data("turn-status", {"status": "busy"})

        yield _emit_stream_error(
            message=user_message,
            error_kind=error_kind,
            error_code=error_code,
            severity=severity,
            is_expected=is_expected,
            extra=error_extra,
        )
        yield streaming_service.format_data("turn-status", {"status": "idle"})
        yield streaming_service.format_finish_step()
        yield streaming_service.format_finish()
        yield streaming_service.format_done()

    finally:
        # Shield the ENTIRE async cleanup from anyio cancel-scope
        # cancellation.  Starlette's BaseHTTPMiddleware uses anyio task
        # groups; on client disconnect, it cancels the scope with
        # level-triggered cancellation — every unshielded `await` inside
        # the cancelled scope raises CancelledError immediately.  Without
        # this shield the very first `await` (session.rollback) would
        # raise CancelledError, `except Exception` wouldn't catch it
        # (CancelledError is a BaseException), and the rest of the
        # finally block — including session.close() — would never run.
        with anyio.CancelScope(shield=True):
            # Authoritative fallback cleanup for lock/cancel state. Middleware
            # teardown can be skipped on some client-abort paths.
            end_turn(str(chat_id))

            # Release premium reservation if not finalized
            if _premium_request_id and _premium_reserved > 0 and user_id:
                try:
                    from app.services.token_quota_service import TokenQuotaService

                    async with shielded_async_session() as quota_session:
                        await TokenQuotaService.premium_release(
                            db_session=quota_session,
                            user_id=UUID(user_id),
                            reserved_tokens=_premium_reserved,
                        )
                    _premium_reserved = 0
                except Exception:
                    logging.getLogger(__name__).warning(
                        "Failed to release premium quota for user %s", user_id
                    )

            try:
                await session.rollback()
                await clear_ai_responding(session, chat_id)
            except Exception:
                try:
                    async with shielded_async_session() as fresh_session:
                        await clear_ai_responding(fresh_session, chat_id)
                except Exception:
                    logging.getLogger(__name__).warning(
                        "Failed to clear AI responding state for thread %s", chat_id
                    )

            with contextlib.suppress(Exception):
                session.expunge_all()

            with contextlib.suppress(Exception):
                await session.close()

        # Persist any sandbox-produced files to local storage so they
        # remain downloadable after the Daytona sandbox auto-deletes.
        if stream_result and stream_result.sandbox_files:
            with contextlib.suppress(Exception):
                from app.agents.new_chat.sandbox import (
                    is_sandbox_enabled,
                    persist_and_delete_sandbox,
                )

                if is_sandbox_enabled():
                    with anyio.CancelScope(shield=True):
                        await persist_and_delete_sandbox(
                            chat_id, stream_result.sandbox_files
                        )

        # Break circular refs held by the agent graph, tools, and LLM
        # wrappers so the GC can reclaim them in a single pass.
        agent = llm = connector_service = None
        input_state = stream_result = None
        session = None

        collected = gc.collect(0) + gc.collect(1) + gc.collect(2)
        if collected:
            _perf_log.info(
                "[stream_new_chat] gc.collect() reclaimed %d objects (chat_id=%s)",
                collected,
                chat_id,
            )
        trim_native_heap()
        log_system_snapshot("stream_new_chat_END")


async def stream_resume_chat(
    chat_id: int,
    search_space_id: int,
    decisions: list[dict],
    user_id: str | None = None,
    llm_config_id: int = -1,
    thread_visibility: ChatVisibility | None = None,
    filesystem_selection: FilesystemSelection | None = None,
    request_id: str | None = None,
) -> AsyncGenerator[str, None]:
    streaming_service = VercelStreamingService()
    stream_result = StreamResult()
    _t_total = time.perf_counter()
    fs_mode = filesystem_selection.mode.value if filesystem_selection else "cloud"
    fs_platform = (
        filesystem_selection.client_platform.value if filesystem_selection else "web"
    )
    stream_result.request_id = request_id
    stream_result.turn_id = f"{chat_id}:{int(time.time() * 1000)}"
    stream_result.filesystem_mode = fs_mode
    stream_result.client_platform = fs_platform
    _log_file_contract("turn_start", stream_result)
    _perf_log.info(
        "[stream_resume] filesystem_mode=%s client_platform=%s",
        fs_mode,
        fs_platform,
    )

    from app.services.token_tracking_service import start_turn

    accumulator = start_turn()

    _emit_stream_error = partial(
        _emit_stream_terminal_error,
        streaming_service=streaming_service,
        flow="resume",
        request_id=request_id,
        thread_id=chat_id,
        search_space_id=search_space_id,
        user_id=user_id,
    )

    session = async_session_maker()
    try:
        if user_id:
            await set_ai_responding(session, chat_id, UUID(user_id))

        agent_config: AgentConfig | None = None
        requested_llm_config_id = llm_config_id

        async def _load_llm_bundle(
            config_id: int,
        ) -> tuple[Any, AgentConfig | None, str | None]:
            if config_id >= 0:
                loaded_agent_config = await load_agent_config(
                    session=session,
                    config_id=config_id,
                    search_space_id=search_space_id,
                )
                if not loaded_agent_config:
                    return (
                        None,
                        None,
                        f"Failed to load NewLLMConfig with id {config_id}",
                    )
                return (
                    create_chat_litellm_from_agent_config(loaded_agent_config),
                    loaded_agent_config,
                    None,
                )

            loaded_llm_config = load_global_llm_config_by_id(config_id)
            if not loaded_llm_config:
                return None, None, f"Failed to load LLM config with id {config_id}"
            return (
                create_chat_litellm_from_config(loaded_llm_config),
                AgentConfig.from_yaml_config(loaded_llm_config),
                None,
            )

        _t0 = time.perf_counter()
        try:
            llm_config_id = (
                await resolve_or_get_pinned_llm_config_id(
                    session,
                    thread_id=chat_id,
                    search_space_id=search_space_id,
                    user_id=user_id,
                    selected_llm_config_id=llm_config_id,
                )
            ).resolved_llm_config_id
        except ValueError as pin_error:
            yield _emit_stream_error(
                message=str(pin_error),
                error_kind="server_error",
                error_code="SERVER_ERROR",
            )
            yield streaming_service.format_done()
            return

        llm, agent_config, llm_load_error = await _load_llm_bundle(llm_config_id)
        if llm_load_error:
            yield _emit_stream_error(
                message=llm_load_error,
                error_kind="server_error",
                error_code="SERVER_ERROR",
            )
            yield streaming_service.format_done()
            return
        _perf_log.info(
            "[stream_resume] LLM config loaded in %.3fs", time.perf_counter() - _t0
        )

        # Premium quota reservation (same logic as stream_new_chat)
        _resume_premium_reserved = 0
        _resume_premium_request_id: str | None = None
        _resume_needs_premium = (
            agent_config is not None and user_id and agent_config.is_premium
        )
        if _resume_needs_premium:
            import uuid as _uuid

            from app.config import config as _app_config
            from app.services.token_quota_service import TokenQuotaService

            _resume_premium_request_id = _uuid.uuid4().hex[:16]
            reserve_amount = min(
                agent_config.quota_reserve_tokens
                or _app_config.QUOTA_MAX_RESERVE_PER_CALL,
                _app_config.QUOTA_MAX_RESERVE_PER_CALL,
            )
            async with shielded_async_session() as quota_session:
                quota_result = await TokenQuotaService.premium_reserve(
                    db_session=quota_session,
                    user_id=UUID(user_id),
                    request_id=_resume_premium_request_id,
                    reserve_tokens=reserve_amount,
                )
            _resume_premium_reserved = reserve_amount
            if not quota_result.allowed:
                if requested_llm_config_id == 0:
                    try:
                        llm_config_id = (
                            await resolve_or_get_pinned_llm_config_id(
                                session,
                                thread_id=chat_id,
                                search_space_id=search_space_id,
                                user_id=user_id,
                                selected_llm_config_id=0,
                                force_repin_free=True,
                            )
                        ).resolved_llm_config_id
                    except ValueError as pin_error:
                        yield _emit_stream_error(
                            message=str(pin_error),
                            error_kind="server_error",
                            error_code="SERVER_ERROR",
                        )
                        yield streaming_service.format_done()
                        return

                    llm, agent_config, llm_load_error = await _load_llm_bundle(
                        llm_config_id
                    )
                    if llm_load_error:
                        yield _emit_stream_error(
                            message=llm_load_error,
                            error_kind="server_error",
                            error_code="SERVER_ERROR",
                        )
                        yield streaming_service.format_done()
                        return
                    _resume_premium_request_id = None
                    _resume_premium_reserved = 0
                    _log_chat_stream_error(
                        flow="resume",
                        error_kind="premium_quota_exhausted",
                        error_code="PREMIUM_QUOTA_EXHAUSTED",
                        severity="info",
                        is_expected=True,
                        request_id=request_id,
                        thread_id=chat_id,
                        search_space_id=search_space_id,
                        user_id=user_id,
                        message=(
                            "Premium quota exhausted on pinned model; auto-fallback switched to a free model"
                        ),
                        extra={
                            "fallback_config_id": llm_config_id,
                            "auto_fallback": True,
                        },
                    )
                else:
                    yield _emit_stream_error(
                        message=(
                            "Buy more tokens to continue with this model, or switch to a free model"
                        ),
                        error_kind="premium_quota_exhausted",
                        error_code="PREMIUM_QUOTA_EXHAUSTED",
                        severity="info",
                        is_expected=True,
                        extra={
                            "resolved_config_id": llm_config_id,
                            "auto_fallback": False,
                        },
                    )
                    yield streaming_service.format_done()
                    return

        if not llm:
            yield _emit_stream_error(
                message="Failed to create LLM instance",
                error_kind="server_error",
                error_code="SERVER_ERROR",
            )
            yield streaming_service.format_done()
            return

        _t0 = time.perf_counter()
        connector_service = ConnectorService(session, search_space_id=search_space_id)

        firecrawl_api_key = None
        webcrawler_connector = await connector_service.get_connector_by_type(
            SearchSourceConnectorType.WEBCRAWLER_CONNECTOR, search_space_id
        )
        if webcrawler_connector and webcrawler_connector.config:
            firecrawl_api_key = webcrawler_connector.config.get("FIRECRAWL_API_KEY")
        _perf_log.info(
            "[stream_resume] Connector service + firecrawl key in %.3fs",
            time.perf_counter() - _t0,
        )

        _t0 = time.perf_counter()
        checkpointer = await get_checkpointer()
        _perf_log.info(
            "[stream_resume] Checkpointer ready in %.3fs", time.perf_counter() - _t0
        )

        visibility = thread_visibility or ChatVisibility.PRIVATE

        _t0 = time.perf_counter()
        agent = await create_surfsense_deep_agent(
            llm=llm,
            search_space_id=search_space_id,
            db_session=session,
            connector_service=connector_service,
            checkpointer=checkpointer,
            user_id=user_id,
            thread_id=chat_id,
            agent_config=agent_config,
            firecrawl_api_key=firecrawl_api_key,
            thread_visibility=visibility,
            filesystem_selection=filesystem_selection,
        )
        _perf_log.info(
            "[stream_resume] Agent created in %.3fs", time.perf_counter() - _t0
        )

        # Release the transaction before streaming (same rationale as stream_new_chat).
        await session.commit()
        session.expunge_all()

        _perf_log.info(
            "[stream_resume] Total pre-stream setup in %.3fs (chat_id=%s)",
            time.perf_counter() - _t_total,
            chat_id,
        )

        from langgraph.types import Command

        config = {
            "configurable": {
                "thread_id": str(chat_id),
                "request_id": request_id or "unknown",
                "turn_id": stream_result.turn_id,
            },
            # See ``stream_new_chat`` above for rationale: effectively
            # uncapped to mirror the agent default and OpenCode's
            # session loop. Doom-loop / call-limit middleware enforce
            # the real ceiling.
            "recursion_limit": 10_000,
        }

        yield streaming_service.format_message_start()
        yield streaming_service.format_start_step()
        # Same rationale as ``stream_new_chat``: emit the turn id so
        # resumed streams can be persisted with their correlation id
        # intact.
        yield streaming_service.format_data(
            "turn-info",
            {"chat_turn_id": stream_result.turn_id},
        )
        yield streaming_service.format_data("turn-status", {"status": "busy"})

        _t_stream_start = time.perf_counter()
        _first_event_logged = False
        runtime_rate_limit_recovered = False
        while True:
            try:
                async for sse in _stream_agent_events(
                    agent=agent,
                    config=config,
                    input_data=Command(resume={"decisions": decisions}),
                    streaming_service=streaming_service,
                    result=stream_result,
                    step_prefix="thinking-resume",
                    fallback_commit_search_space_id=search_space_id,
                    fallback_commit_created_by_id=user_id,
                    fallback_commit_filesystem_mode=(
                        filesystem_selection.mode
                        if filesystem_selection
                        else FilesystemMode.CLOUD
                    ),
                    fallback_commit_thread_id=chat_id,
                ):
                    if not _first_event_logged:
                        _perf_log.info(
                            "[stream_resume] First agent event in %.3fs (stream), %.3fs (total) (chat_id=%s)",
                            time.perf_counter() - _t_stream_start,
                            time.perf_counter() - _t_total,
                            chat_id,
                        )
                        _first_event_logged = True
                    yield sse
                break
            except Exception as stream_exc:
                can_runtime_recover = (
                    not runtime_rate_limit_recovered
                    and requested_llm_config_id == 0
                    and llm_config_id < 0
                    and not _first_event_logged
                    and _is_provider_rate_limited(stream_exc)
                )
                if not can_runtime_recover:
                    raise

                runtime_rate_limit_recovered = True
                previous_config_id = llm_config_id
                # Ensure the same-request recovery retry does not trip the
                # BusyMutex lock retained by the failed attempt.
                end_turn(str(chat_id))
                mark_runtime_cooldown(
                    previous_config_id,
                    reason="provider_rate_limited",
                )
                llm_config_id = (
                    await resolve_or_get_pinned_llm_config_id(
                        session,
                        thread_id=chat_id,
                        search_space_id=search_space_id,
                        user_id=user_id,
                        selected_llm_config_id=0,
                        exclude_config_ids={previous_config_id},
                    )
                ).resolved_llm_config_id

                llm, agent_config, llm_load_error = await _load_llm_bundle(llm_config_id)
                if llm_load_error:
                    raise stream_exc

                _t0 = time.perf_counter()
                agent = await create_surfsense_deep_agent(
                    llm=llm,
                    search_space_id=search_space_id,
                    db_session=session,
                    connector_service=connector_service,
                    checkpointer=checkpointer,
                    user_id=user_id,
                    thread_id=chat_id,
                    agent_config=agent_config,
                    firecrawl_api_key=firecrawl_api_key,
                    thread_visibility=visibility,
                    filesystem_selection=filesystem_selection,
                )
                _perf_log.info(
                    "[stream_resume] Runtime rate-limit recovery repinned "
                    "config_id=%s -> %s and rebuilt agent in %.3fs",
                    previous_config_id,
                    llm_config_id,
                    time.perf_counter() - _t0,
                )
                _log_chat_stream_error(
                    flow="resume",
                    error_kind="rate_limited",
                    error_code="RATE_LIMITED",
                    severity="info",
                    is_expected=True,
                    request_id=request_id,
                    thread_id=chat_id,
                    search_space_id=search_space_id,
                    user_id=user_id,
                    message=(
                        "Auto-pinned model hit runtime rate limit; switched to "
                        "another eligible model and retried."
                    ),
                    extra={
                        "auto_runtime_recover": True,
                        "previous_config_id": previous_config_id,
                        "fallback_config_id": llm_config_id,
                    },
                )
                continue
        _perf_log.info(
            "[stream_resume] Agent stream completed in %.3fs (chat_id=%s)",
            time.perf_counter() - _t_stream_start,
            chat_id,
        )
        if stream_result.is_interrupted:
            usage_summary = accumulator.per_message_summary()
            _perf_log.info(
                "[token_usage] interrupted resume_chat: calls=%d total=%d summary=%s",
                len(accumulator.calls),
                accumulator.grand_total,
                usage_summary,
            )
            if usage_summary:
                yield streaming_service.format_data(
                    "token-usage",
                    {
                        "usage": usage_summary,
                        "prompt_tokens": accumulator.total_prompt_tokens,
                        "completion_tokens": accumulator.total_completion_tokens,
                        "total_tokens": accumulator.grand_total,
                        "call_details": accumulator.serialized_calls(),
                    },
                )

            yield streaming_service.format_finish_step()
            yield streaming_service.format_finish()
            yield streaming_service.format_done()
            return

        # Finalize premium quota for resume path
        if _resume_premium_request_id and user_id:
            try:
                from app.services.token_quota_service import TokenQuotaService

                async with shielded_async_session() as quota_session:
                    await TokenQuotaService.premium_finalize(
                        db_session=quota_session,
                        user_id=UUID(user_id),
                        request_id=_resume_premium_request_id,
                        actual_tokens=accumulator.grand_total,
                        reserved_tokens=_resume_premium_reserved,
                    )
                _resume_premium_request_id = None
                _resume_premium_reserved = 0
            except Exception:
                logging.getLogger(__name__).warning(
                    "Failed to finalize premium quota for user %s (resume)",
                    user_id,
                    exc_info=True,
                )

        usage_summary = accumulator.per_message_summary()
        _perf_log.info(
            "[token_usage] normal resume_chat: calls=%d total=%d summary=%s",
            len(accumulator.calls),
            accumulator.grand_total,
            usage_summary,
        )
        if usage_summary:
            yield streaming_service.format_data(
                "token-usage",
                {
                    "usage": usage_summary,
                    "prompt_tokens": accumulator.total_prompt_tokens,
                    "completion_tokens": accumulator.total_completion_tokens,
                    "total_tokens": accumulator.grand_total,
                    "call_details": accumulator.serialized_calls(),
                },
            )

        yield streaming_service.format_data("turn-status", {"status": "idle"})
        yield streaming_service.format_finish_step()
        yield streaming_service.format_finish()
        yield streaming_service.format_done()

    except Exception as e:
        import traceback

        (
            error_kind,
            error_code,
            severity,
            is_expected,
            user_message,
            error_extra,
        ) = _classify_stream_exception(e, flow_label="resume")
        error_message = f"Error during resume: {e!s}"
        print(f"[stream_resume_chat] {error_message}")
        print(f"[stream_resume_chat] Traceback:\n{traceback.format_exc()}")
        if error_code == "TURN_CANCELLING":
            status_payload: dict[str, Any] = {"status": "cancelling"}
            if error_extra:
                status_payload.update(error_extra)
            yield streaming_service.format_data("turn-status", status_payload)
        else:
            yield streaming_service.format_data("turn-status", {"status": "busy"})
        yield _emit_stream_error(
            message=user_message,
            error_kind=error_kind,
            error_code=error_code,
            severity=severity,
            is_expected=is_expected,
            extra=error_extra,
        )
        yield streaming_service.format_data("turn-status", {"status": "idle"})
        yield streaming_service.format_finish_step()
        yield streaming_service.format_finish()
        yield streaming_service.format_done()

    finally:
        with anyio.CancelScope(shield=True):
            # Authoritative fallback cleanup for lock/cancel state. Middleware
            # teardown can be skipped on some client-abort paths.
            end_turn(str(chat_id))

            # Release premium reservation if not finalized
            if _resume_premium_request_id and _resume_premium_reserved > 0 and user_id:
                try:
                    from app.services.token_quota_service import TokenQuotaService

                    async with shielded_async_session() as quota_session:
                        await TokenQuotaService.premium_release(
                            db_session=quota_session,
                            user_id=UUID(user_id),
                            reserved_tokens=_resume_premium_reserved,
                        )
                    _resume_premium_reserved = 0
                except Exception:
                    logging.getLogger(__name__).warning(
                        "Failed to release premium quota for user %s (resume)", user_id
                    )

            try:
                await session.rollback()
                await clear_ai_responding(session, chat_id)
            except Exception:
                try:
                    async with shielded_async_session() as fresh_session:
                        await clear_ai_responding(fresh_session, chat_id)
                except Exception:
                    logging.getLogger(__name__).warning(
                        "Failed to clear AI responding state for thread %s", chat_id
                    )

            with contextlib.suppress(Exception):
                session.expunge_all()

            with contextlib.suppress(Exception):
                await session.close()

        agent = llm = connector_service = None
        stream_result = None
        session = None

        collected = gc.collect(0) + gc.collect(1) + gc.collect(2)
        if collected:
            _perf_log.info(
                "[stream_resume] gc.collect() reclaimed %d objects (chat_id=%s)",
                collected,
                chat_id,
            )
        trim_native_heap()
        log_system_snapshot("stream_resume_chat_END")
