"""
Streaming task for the new SurfSense deep agent chat.

This module streams responses from the deep agent using the Vercel AI SDK
Data Stream Protocol (SSE format).

Supports loading LLM configurations from:
- YAML files (negative IDs for global configs)
- NewLLMConfig database table (positive IDs for user-created configs with prompt settings)
"""

import asyncio
import contextlib
import gc
import json
import logging
import time
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from functools import partial
from typing import Any, Literal
from uuid import UUID

import anyio
from langchain_core.messages import HumanMessage
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.agents.multi_agent_chat import create_multi_agent_chat_deep_agent
from app.agents.new_chat.chat_deepagent import create_surfsense_deep_agent
from app.agents.new_chat.checkpointer import get_checkpointer
from app.agents.new_chat.context import SurfSenseContextSchema
from app.agents.new_chat.errors import BusyError
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
from app.agents.new_chat.mention_resolver import resolve_mentions, substitute_in_text
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
    is_recently_healthy,
    mark_healthy,
    mark_runtime_cooldown,
    resolve_or_get_pinned_llm_config_id,
)
from app.services.chat_session_state_service import (
    clear_ai_responding,
    set_ai_responding,
)
from app.services.connector_service import ConnectorService
from app.services.new_streaming_service import VercelStreamingService
from app.tasks.chat.streaming.graph_stream.event_stream import stream_output
from app.utils.content_utils import bootstrap_history_from_db
from app.utils.perf import get_perf_logger, log_system_snapshot, trim_native_heap
from app.utils.user_message_multimodal import build_human_message_content

_background_tasks: set[asyncio.Task] = set()
_perf_log = get_perf_logger()
logger = logging.getLogger(__name__)

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


def _first_interrupt_value(state: Any) -> dict[str, Any] | None:
    """Return the first LangGraph interrupt payload across all snapshot tasks."""

    def _extract_interrupt_value(candidate: Any) -> dict[str, Any] | None:
        if isinstance(candidate, dict):
            value = candidate.get("value", candidate)
            return value if isinstance(value, dict) else None
        value = getattr(candidate, "value", None)
        if isinstance(value, dict):
            return value
        if isinstance(candidate, (list, tuple)):
            for item in candidate:
                extracted = _extract_interrupt_value(item)
                if extracted is not None:
                    return extracted
        return None

    for task in getattr(state, "tasks", ()) or ():
        try:
            interrupts = getattr(task, "interrupts", ()) or ()
        except (AttributeError, IndexError, TypeError):
            interrupts = ()
        if not interrupts:
            extracted = _extract_interrupt_value(task)
            if extracted is not None:
                return extracted
            continue
        for interrupt_item in interrupts:
            extracted = _extract_interrupt_value(interrupt_item)
            if extracted is not None:
                return extracted
    try:
        state_interrupts = getattr(state, "interrupts", ()) or ()
    except (AttributeError, IndexError, TypeError):
        state_interrupts = ()
    extracted = _extract_interrupt_value(state_interrupts)
    if extracted is not None:
        return extracted
    return None


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
    # Pre-allocated assistant ``new_chat_messages.id`` for this turn,
    # captured by ``persist_assistant_shell`` right after the user row is
    # persisted. ``None`` for the legacy / anonymous code paths that don't
    # opt in to server-side ``ContentPart[]`` projection.
    assistant_message_id: int | None = None
    # In-memory mirror of the FE's assistant-ui ``ContentPartsState``,
    # populated by the lifecycle methods called from ``_stream_agent_events``
    # at each ``streaming_service.format_*`` yield site. Snapshot in the
    # streaming ``finally`` to produce the rich JSONB persisted by
    # ``finalize_assistant_turn``. ``repr=False`` keeps the
    # log-on-error path (``StreamResult`` is logged in some error
    # branches) from dumping a potentially-large parts list.
    content_builder: Any | None = field(default=None, repr=False)


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


def _extract_resolved_file_path(
    *, tool_name: str, tool_output: Any, tool_input: Any | None = None
) -> str | None:
    if isinstance(tool_output, dict):
        path_value = tool_output.get("path")
        if isinstance(path_value, str) and path_value.strip():
            return path_value.strip()
    if tool_name in ("write_file", "edit_file") and isinstance(tool_input, dict):
        file_path = tool_input.get("file_path")
        if isinstance(file_path, str) and file_path.strip():
            return file_path.strip()
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


_PREFLIGHT_TIMEOUT_SEC: float = 2.5
_PREFLIGHT_MAX_TOKENS: int = 1


async def _preflight_llm(llm: Any) -> None:
    """Issue a minimal completion to confirm the pinned model isn't 429'ing.

    Used before agent build / planner / classifier / title-gen so a known-bad
    free OpenRouter deployment is detected and repinned before it cascades
    into multiple wasted internal calls. The probe is intentionally cheap:
    one token, low timeout, tagged ``surfsense:internal`` so token tracking
    and SSE pipelines treat it as overhead rather than user output.

    Raises the original exception when the provider responds with a
    rate-limit-shaped error so the caller can drive the cooldown/repin
    branch via :func:`_is_provider_rate_limited`. Other transient failures
    are swallowed — the caller continues to the normal stream path and the
    in-stream recovery loop remains the safety net.
    """
    from litellm import acompletion

    model = getattr(llm, "model", None)
    if not model or model == "auto":
        # Auto-mode router doesn't have a single deployment to ping; the
        # router itself handles per-deployment rate-limit accounting.
        return

    try:
        await acompletion(
            model=model,
            messages=[{"role": "user", "content": "ping"}],
            api_key=getattr(llm, "api_key", None),
            api_base=getattr(llm, "api_base", None),
            max_tokens=_PREFLIGHT_MAX_TOKENS,
            timeout=_PREFLIGHT_TIMEOUT_SEC,
            stream=False,
            metadata={"tags": ["surfsense:internal", "auto-pin-preflight"]},
        )
    except Exception as exc:
        if _is_provider_rate_limited(exc):
            raise
        logging.getLogger(__name__).debug(
            "auto_pin_preflight non_rate_limit_error model=%s err=%s",
            model,
            exc,
        )


async def _build_main_agent_for_thread(
    agent_factory: Any,
    *,
    llm: Any,
    search_space_id: int,
    db_session: Any,
    connector_service: ConnectorService,
    checkpointer: Any,
    user_id: str | None,
    thread_id: int | None,
    agent_config: AgentConfig | None,
    firecrawl_api_key: str | None,
    thread_visibility: ChatVisibility | None,
    filesystem_selection: FilesystemSelection | None,
    disabled_tools: list[str] | None = None,
    mentioned_document_ids: list[int] | None = None,
) -> Any:
    """Single (re)build path so the agent factory cannot drift across
    initial build, preflight repin, and mid-stream 429 recovery for one
    ``thread_id``: a graph swap mid-turn would corrupt checkpointer state."""
    return await agent_factory(
        llm=llm,
        search_space_id=search_space_id,
        db_session=db_session,
        connector_service=connector_service,
        checkpointer=checkpointer,
        user_id=user_id,
        thread_id=thread_id,
        agent_config=agent_config,
        firecrawl_api_key=firecrawl_api_key,
        thread_visibility=thread_visibility,
        filesystem_selection=filesystem_selection,
        disabled_tools=disabled_tools,
        mentioned_document_ids=mentioned_document_ids,
    )


async def _settle_speculative_agent_build(task: asyncio.Task[Any]) -> None:
    """Wait for a discarded speculative agent build to release shared state.

    Used by the parallel preflight + agent-build path. The speculative build
    closes over the request-scoped ``AsyncSession`` (for the brief connector
    discovery / tool-factory window before its CPU work moves into a worker
    thread). If preflight reports a 429 we want to fall back to the original
    repin → reload → rebuild path, but we MUST NOT touch ``session`` again
    until any in-flight session work owned by the speculative build has
    fully settled — :class:`sqlalchemy.ext.asyncio.AsyncSession` is not
    concurrency-safe and the same hazard cost us a hard ``InvalidRequestError``
    earlier in this PR (see ``connector_service`` parallel-gather revert).

    We simply ``await`` the task and swallow any exception: in this path the
    build's outcome is irrelevant — success populates the agent cache (a free
    side effect), failure is discarded. The wasted CPU is acceptable since
    429 fallbacks are rare and the original sequential code also paid the
    full build cost on the same path.
    """
    with contextlib.suppress(BaseException):
        await task


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

    Pure extract of the in-line match used at ``on_tool_start`` when the
    chunk path didn't register an index for this call. Pops the next
    id-bearing chunk whose ``name``
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
    runtime_context: Any = None,
    content_builder: Any | None = None,
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
        content_builder: Optional ``AssistantContentBuilder``. When set, every
            ``streaming_service.format_*`` yield site also drives the matching
            builder lifecycle method (``on_text_*``, ``on_reasoning_*``,
            ``on_tool_*``, ``on_thinking_step``, ``on_step_separator``) so the
            in-memory ``ContentPart[]`` projection stays in lockstep with what
            the FE renders live. Pure in-memory accumulation — no DB I/O —
            consumed by the streaming ``finally`` to produce the rich JSONB
            persisted via ``finalize_assistant_turn``. ``None`` (the default)
            is used by the anonymous / legacy code paths and is a no-op.

    Yields:
        SSE-formatted strings for each event.
    """
    async for sse in stream_output(
        agent=agent,
        config=config,
        input_data=input_data,
        streaming_service=streaming_service,
        result=result,
        step_prefix=step_prefix,
        initial_step_id=initial_step_id,
        initial_step_title=initial_step_title,
        initial_step_items=initial_step_items,
        content_builder=content_builder,
        runtime_context=runtime_context,
    ):
        yield sse

    accumulated_text = result.accumulated_text

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
            if content_builder is not None:
                content_builder.on_text_start(gate_text_id)
            yield streaming_service.format_text_delta(gate_text_id, gate_notice)
            if content_builder is not None:
                content_builder.on_text_delta(gate_text_id, gate_notice)
            yield streaming_service.format_text_end(gate_text_id)
            if content_builder is not None:
                content_builder.on_text_end(gate_text_id)
            yield streaming_service.format_terminal_info(gate_notice, "error")
            accumulated_text = gate_notice
    else:
        result.commit_gate_passed = True
        result.commit_gate_reason = ""

    result.accumulated_text = accumulated_text
    _log_file_contract("turn_outcome", result)

    interrupt_value = _first_interrupt_value(state)
    if interrupt_value is not None:
        result.is_interrupted = True
        result.interrupt_value = interrupt_value
        yield streaming_service.format_interrupt_request(result.interrupt_value)


async def stream_new_chat(
    user_query: str,
    search_space_id: int,
    chat_id: int,
    user_id: str | None = None,
    llm_config_id: int = -1,
    mentioned_document_ids: list[int] | None = None,
    mentioned_surfsense_doc_ids: list[int] | None = None,
    mentioned_folder_ids: list[int] | None = None,
    mentioned_documents: list[dict[str, Any]] | None = None,
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
        mentioned_folder_ids: Optional list of knowledge-base folder IDs mentioned with @ (cloud mode)
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

    # Premium credit (USD micro-units) tracking state. Stores the
    # amount reserved up front so we can release it on cancellation
    # and finalize-debit the actual provider cost reported by LiteLLM.
    _premium_reserved_micros = 0
    _premium_request_id: str | None = None

    # ``BusyError`` fires before the lock is acquired; the ``finally`` must
    # not release the in-flight caller's lock.
    _busy_error_raised = False

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
        # Image-bearing turns force the Auto-pin resolver to filter the
        # candidate pool to vision-capable cfgs (and force-repin a
        # text-only existing pin). For explicit selections this flag is
        # a no-op — the resolver returns the user's chosen id unchanged.
        _requires_image_input = bool(user_image_data_urls)
        try:
            llm_config_id = (
                await resolve_or_get_pinned_llm_config_id(
                    session,
                    thread_id=chat_id,
                    search_space_id=search_space_id,
                    user_id=user_id,
                    selected_llm_config_id=llm_config_id,
                    requires_image_input=_requires_image_input,
                )
            ).resolved_llm_config_id
        except ValueError as pin_error:
            # Auto-pin's "no vision-capable cfg" path raises a ValueError
            # whose message we map to the friendly image-input SSE error
            # so the user sees the same message regardless of whether
            # the gate fired in Auto-mode or in the agent_config check
            # below.
            error_code = (
                "MODEL_DOES_NOT_SUPPORT_IMAGE_INPUT"
                if _requires_image_input and "vision-capable" in str(pin_error)
                else "SERVER_ERROR"
            )
            error_kind = (
                "user_error"
                if error_code == "MODEL_DOES_NOT_SUPPORT_IMAGE_INPUT"
                else "server_error"
            )
            yield _emit_stream_error(
                message=str(pin_error),
                error_kind=error_kind,
                error_code=error_code,
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

        # Capability safety net: a turn carrying user-uploaded images
        # cannot be routed to a chat config that LiteLLM's authoritative
        # model map *explicitly* marks as text-only (``supports_vision``
        # set to False). The check is intentionally narrow — it only
        # fires when LiteLLM is *certain* the model can't accept image
        # input. Unknown / unmapped / vision-capable models pass
        # through. Without this guard a known-text-only model would 404
        # at the provider with ``"No endpoints found that support image
        # input"``, surfacing as an opaque ``SERVER_ERROR`` SSE chunk;
        # failing here lets us return a friendly message that tells the
        # user what to change.
        if user_image_data_urls and agent_config is not None:
            from app.services.provider_capabilities import (
                is_known_text_only_chat_model,
            )

            agent_litellm_params = agent_config.litellm_params or {}
            agent_base_model = (
                agent_litellm_params.get("base_model")
                if isinstance(agent_litellm_params, dict)
                else None
            )
            if is_known_text_only_chat_model(
                provider=agent_config.provider,
                model_name=agent_config.model_name,
                base_model=agent_base_model,
                custom_provider=agent_config.custom_provider,
            ):
                model_label = (
                    agent_config.config_name or agent_config.model_name or "model"
                )
                yield _emit_stream_error(
                    message=(
                        f"The selected model ({model_label}) does not support "
                        "image input. Switch to a vision-capable model "
                        "(e.g. GPT-4o, Claude, Gemini) or remove the image "
                        "attachment and try again."
                    ),
                    error_kind="user_error",
                    error_code="MODEL_DOES_NOT_SUPPORT_IMAGE_INPUT",
                )
                yield streaming_service.format_done()
                return

        # Premium quota reservation for pinned premium model only.
        _needs_premium_quota = (
            agent_config is not None and user_id and agent_config.is_premium
        )
        if _needs_premium_quota:
            import uuid as _uuid

            from app.services.token_quota_service import (
                TokenQuotaService,
                estimate_call_reserve_micros,
            )

            _premium_request_id = _uuid.uuid4().hex[:16]
            _agent_litellm_params = agent_config.litellm_params or {}
            _agent_base_model = (
                _agent_litellm_params.get("base_model") or agent_config.model_name or ""
            )
            reserve_amount_micros = estimate_call_reserve_micros(
                base_model=_agent_base_model,
                quota_reserve_tokens=agent_config.quota_reserve_tokens,
            )
            async with shielded_async_session() as quota_session:
                quota_result = await TokenQuotaService.premium_reserve(
                    db_session=quota_session,
                    user_id=UUID(user_id),
                    request_id=_premium_request_id,
                    reserve_micros=reserve_amount_micros,
                )
            _premium_reserved_micros = reserve_amount_micros
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
                                requires_image_input=_requires_image_input,
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
                    _premium_reserved_micros = 0
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

        # Auto-mode preflight ping. Runs ONLY for thread-pinned auto cfgs
        # (negative ids selected via ``resolve_or_get_pinned_llm_config_id``)
        # whose health hasn't already been confirmed within the TTL window.
        # Detecting a 429 here lets us repin BEFORE the planner/classifier/
        # title-generation LLM calls fan out and each independently hit the
        # same upstream rate limit.
        #
        # PERF: preflight is a network round-trip to the LLM provider (~1-5s)
        # and is independent of the agent build (CPU-bound, ~5-7s). They used
        # to run sequentially → ``preflight + build`` on cold cache = 11.5s.
        # We now kick off preflight as a background task FIRST, then run the
        # synchronous setup work and the agent build in parallel. In the
        # success path (the common case) total wall time drops to roughly
        # ``max(preflight, build)`` — the preflight finishes during the
        # agent compile and we just consume its result. In the rare 429
        # path the speculative build is awaited to completion (so its
        # session usage is fully released) via
        # :func:`_settle_speculative_agent_build`, then discarded, and
        # we fall back to the original repin-and-rebuild flow.
        preflight_needed = (
            requested_llm_config_id == 0
            and llm_config_id < 0
            and not is_recently_healthy(llm_config_id)
        )
        preflight_task: asyncio.Task[None] | None = None
        _t_preflight = 0.0
        if preflight_needed:
            _t_preflight = time.perf_counter()
            preflight_task = asyncio.create_task(
                _preflight_llm(llm),
                name=f"auto_pin_preflight:{llm_config_id}",
            )

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
        from app.config import config as _app_config

        use_multi_agent = bool(_app_config.MULTI_AGENT_CHAT_ENABLED)

        _t0 = time.perf_counter()
        agent_factory = (
            create_multi_agent_chat_deep_agent
            if use_multi_agent
            else create_surfsense_deep_agent
        )
        # Speculative agent build — runs in parallel with the preflight
        # task (if any). Built with the *current* ``llm`` / ``agent_config``;
        # if preflight reports 429 we will discard this future and rebuild
        # against the freshly pinned config below.
        agent_build_task = asyncio.create_task(
            _build_main_agent_for_thread(
                agent_factory,
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
                disabled_tools=disabled_tools,
                mentioned_document_ids=mentioned_document_ids,
            ),
            name="agent_build:stream_new_chat",
        )

        agent: Any = None
        if preflight_task is not None:
            try:
                await preflight_task
                mark_healthy(llm_config_id)
                _perf_log.info(
                    "[stream_new_chat] auto_pin_preflight ok config_id=%s took=%.3fs (parallel)",
                    llm_config_id,
                    time.perf_counter() - _t_preflight,
                )
            except Exception as preflight_exc:
                # Both branches below need the session: the non-429 path
                # may unwind via cleanup that uses ``session``, and the
                # 429 path explicitly calls ``resolve_or_get_pinned_llm_config_id``
                # against it. Wait for the speculative build to release its
                # session usage before we proceed.
                await _settle_speculative_agent_build(agent_build_task)
                if not _is_provider_rate_limited(preflight_exc):
                    raise
                # 429: speculative agent is discarded; run the original
                # repin → reload → rebuild path against the freshly
                # pinned config.
                previous_config_id = llm_config_id
                mark_runtime_cooldown(
                    previous_config_id, reason="preflight_rate_limited"
                )
                try:
                    llm_config_id = (
                        await resolve_or_get_pinned_llm_config_id(
                            session,
                            thread_id=chat_id,
                            search_space_id=search_space_id,
                            user_id=user_id,
                            selected_llm_config_id=0,
                            exclude_config_ids={previous_config_id},
                            requires_image_input=_requires_image_input,
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
                if llm_load_error or not llm:
                    yield _emit_stream_error(
                        message=llm_load_error or "Failed to create LLM instance",
                        error_kind="server_error",
                        error_code="SERVER_ERROR",
                    )
                    yield streaming_service.format_done()
                    return
                # Trust the freshly-resolved cfg for the remainder of this
                # turn rather than recursing into another preflight; the
                # in-stream 429 recovery loop is still in place as the
                # safety net if even this fallback hits an upstream cap.
                mark_healthy(llm_config_id)
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
                        "Auto-pinned model failed preflight; switched to another "
                        "eligible model and continuing."
                    ),
                    extra={
                        "auto_runtime_recover": True,
                        "preflight": True,
                        "previous_config_id": previous_config_id,
                        "fallback_config_id": llm_config_id,
                    },
                )
                # Rebuild against the new llm/agent_config. Sequential
                # here because we no longer have anything to overlap with.
                agent = await agent_factory(
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

        if agent is None:
            # Either no preflight was needed, or preflight succeeded —
            # in both cases the speculative build is the agent we want.
            agent = await agent_build_task
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

        # Resolve @-mention chips to canonical virtual paths and rewrite
        # the user-typed text so the LLM sees ``\`/documents/...\``` instead
        # of bare ``@title``. The persisted user-message text keeps
        # ``@title`` so chip rendering on reload is unchanged — see
        # ``persistence._build_user_content``.
        #
        # Cloud mode only: local-folder mode keeps the legacy
        # ``@title`` text path; mention support there is a follow-up
        # task because the path scheme (mount-rooted) and the picker
        # UI both need separate work.
        accepted_folder_ids: list[int] = []
        if fs_mode == FilesystemMode.CLOUD.value and (
            mentioned_document_ids
            or mentioned_surfsense_doc_ids
            or mentioned_folder_ids
            or mentioned_documents
        ):
            from app.schemas.new_chat import (
                MentionedDocumentInfo as _MentionedDocumentInfo,
            )

            chip_objs: list[_MentionedDocumentInfo] | None = None
            if mentioned_documents:
                chip_objs = []
                for raw in mentioned_documents:
                    if isinstance(raw, _MentionedDocumentInfo):
                        chip_objs.append(raw)
                        continue
                    try:
                        chip_objs.append(_MentionedDocumentInfo.model_validate(raw))
                    except Exception:
                        logger.debug(
                            "stream_new_chat: dropping malformed mention chip %r",
                            raw,
                        )

            resolved = await resolve_mentions(
                session,
                search_space_id=search_space_id,
                mentioned_documents=chip_objs,
                mentioned_document_ids=mentioned_document_ids,
                mentioned_surfsense_doc_ids=mentioned_surfsense_doc_ids,
                mentioned_folder_ids=mentioned_folder_ids,
            )
            user_query = substitute_in_text(user_query, resolved.token_to_path)
            accepted_folder_ids = resolved.mentioned_folder_ids

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

        # Persist the user-side row for this turn before any expensive
        # work runs. Closes the "ghost-thread" abuse vector
        # (authenticated client hits POST /new_chat then never calls
        # /messages — empty new_chat_messages, free LLM completion).
        # Idempotent against the unique index in migration 141 so the
        # legacy frontend appendMessage call is a no-op on the second
        # writer. Hard failure aborts the turn so we never produce a
        # title or assistant row that isn't anchored to a persisted
        # user message.
        from app.tasks.chat.content_builder import AssistantContentBuilder
        from app.tasks.chat.persistence import (
            persist_assistant_shell,
            persist_user_turn,
        )

        user_message_id = await persist_user_turn(
            chat_id=chat_id,
            user_id=user_id,
            turn_id=stream_result.turn_id,
            user_query=user_query,
            user_image_data_urls=user_image_data_urls,
            mentioned_documents=mentioned_documents,
        )
        if user_message_id is None:
            yield _emit_stream_error(
                message=(
                    "We couldn't save your message. Please try again in a moment."
                ),
                error_kind="server_error",
                error_code="MESSAGE_PERSIST_FAILED",
            )
            yield streaming_service.format_data("turn-status", {"status": "idle"})
            yield streaming_service.format_finish_step()
            yield streaming_service.format_finish()
            yield streaming_service.format_done()
            return

        # Emit canonical user message id BEFORE any LLM streaming so the
        # FE can rename its optimistic ``msg-user-XXX`` placeholder to
        # ``msg-{user_message_id}`` and unlock features gated on a real
        # DB id (comments, edit-from-this-message). See B4 in
        # ``sse-based_message_id_handshake`` plan.
        yield streaming_service.format_data(
            "user-message-id",
            {"message_id": user_message_id, "turn_id": stream_result.turn_id},
        )

        # Pre-write the assistant row for this turn so we have a stable
        # ``message_id`` to anchor mid-stream metadata (token_usage,
        # future agent_action_log.message_id correlation) and a
        # write-once UPDATE target at finalize time. Idempotent against
        # the (thread_id, turn_id, ASSISTANT) partial unique index from
        # migration 141 — if the legacy frontend appendMessage races
        # this, we recover the existing row's id.
        assistant_message_id = await persist_assistant_shell(
            chat_id=chat_id,
            user_id=user_id,
            turn_id=stream_result.turn_id,
        )
        if assistant_message_id is None:
            # Genuine DB failure — abort the turn rather than stream
            # into a void. The user row is already persisted so the
            # legacy "ghost-thread" gate isn't reopened.
            yield _emit_stream_error(
                message=(
                    "We couldn't initialize the assistant message. Please try again."
                ),
                error_kind="server_error",
                error_code="MESSAGE_PERSIST_FAILED",
            )
            yield streaming_service.format_data("turn-status", {"status": "idle"})
            yield streaming_service.format_finish_step()
            yield streaming_service.format_finish()
            yield streaming_service.format_done()
            return

        # Emit canonical assistant message id BEFORE any LLM streaming
        # so the FE can rename its optimistic ``msg-assistant-XXX``
        # placeholder to ``msg-{assistant_message_id}`` and bind
        # ``tokenUsageStore`` / ``pendingInterrupt`` to the real id
        # immediately. See B4 in ``sse-based_message_id_handshake``
        # plan.
        yield streaming_service.format_data(
            "assistant-message-id",
            {"message_id": assistant_message_id, "turn_id": stream_result.turn_id},
        )

        stream_result.assistant_message_id = assistant_message_id
        stream_result.content_builder = AssistantContentBuilder()

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

        # Drive the builder for this initial thinking step too — the
        # ``_emit_thinking_step`` helper lives inside ``_stream_agent_events``
        # so it isn't in scope here, but the FE folds this step into
        # the same singleton ``data-thinking-steps`` part as everything
        # the agent stream emits later. Mirror that fold server-side.
        if stream_result.content_builder is not None:
            stream_result.content_builder.on_thinking_step(
                initial_step_id, initial_title, "in_progress", initial_items
            )
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
        # Use a LIMIT 1 EXISTS-style probe rather than COUNT(*) because
        # this is now a hot path executed on every turn, and COUNT scales
        # with thread length (server-side persistence can grow rows
        # quickly under power users).
        #
        # IMPORTANT: ``persist_assistant_shell`` above (line ~3112) already
        # inserted THIS turn's assistant row. We must therefore exclude
        # it from the probe — otherwise the gate fires on every turn
        # except the very first, and title generation never runs for new
        # threads. Excluding by primary key (``id != assistant_message_id``)
        # is bulletproof regardless of ``turn_id`` shape (legacy NULLs,
        # resume turns, etc.).
        first_assistant_probe = await session.execute(
            select(NewChatMessage.id)
            .filter(
                NewChatMessage.thread_id == chat_id,
                NewChatMessage.role == "assistant",
                NewChatMessage.id != assistant_message_id,
            )
            .limit(1)
        )
        is_first_response = first_assistant_probe.scalars().first() is None

        title_task: asyncio.Task[tuple[str | None, dict | None]] | None = None
        # Gate title generation on a persisted user message so a stream
        # that fails before persistence (we abort above) can never leave
        # behind a thread with a generated title and no anchoring rows.
        if is_first_response and user_message_id is not None:

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
                    from app.services.provider_api_base import resolve_api_base
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
                        # Apply the same ``api_base`` cascade chat / vision /
                        # image-gen call sites use so we never inherit
                        # ``litellm.api_base`` (commonly set by
                        # ``AZURE_OPENAI_ENDPOINT``) when the chat config
                        # itself ships an empty ``api_base``. Without this
                        # the title-gen on an OpenRouter chat config would
                        # 404 against the inherited Azure endpoint — see
                        # ``provider_api_base`` docstring for the same
                        # bug repro on the image-gen / vision paths.
                        raw_model = getattr(llm, "model", "") or ""
                        provider_prefix = (
                            raw_model.split("/", 1)[0] if "/" in raw_model else None
                        )
                        provider_value = (
                            agent_config.provider if agent_config is not None else None
                        )
                        title_api_base = resolve_api_base(
                            provider=provider_value,
                            provider_prefix=provider_prefix,
                            config_api_base=getattr(llm, "api_base", None),
                        )
                        response = await acompletion(
                            model=raw_model,
                            messages=messages,
                            api_key=getattr(llm, "api_key", None),
                            api_base=title_api_base,
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

        # Build the per-invocation runtime context (Phase 1.5).
        # ``mentioned_document_ids`` is read by ``KnowledgePriorityMiddleware``
        # via ``runtime.context.mentioned_document_ids`` instead of its
        # ``__init__`` closure — that way the same compiled-agent instance
        # can serve multiple turns with different mention lists.
        runtime_context = SurfSenseContextSchema(
            search_space_id=search_space_id,
            mentioned_document_ids=list(mentioned_document_ids or []),
            mentioned_folder_ids=list(
                accepted_folder_ids or mentioned_folder_ids or []
            ),
            request_id=request_id,
            turn_id=stream_result.turn_id,
        )

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
                    runtime_context=runtime_context,
                    content_builder=stream_result.content_builder,
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
                    if (
                        title_task is not None
                        and title_task.done()
                        and not title_emitted
                    ):
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
                        requires_image_input=_requires_image_input,
                    )
                ).resolved_llm_config_id

                llm, agent_config, llm_load_error = await _load_llm_bundle(
                    llm_config_id
                )
                if llm_load_error:
                    raise stream_exc

                # Title generation uses the initial llm object. After a runtime
                # repin we keep the stream focused on response recovery and skip
                # title generation for this turn.
                if title_task is not None and not title_task.done():
                    title_task.cancel()
                title_task = None

                _t0 = time.perf_counter()
                agent = await _build_main_agent_for_thread(
                    agent_factory,
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
                    disabled_tools=disabled_tools,
                    mentioned_document_ids=mentioned_document_ids,
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
                "[token_usage] interrupted new_chat: calls=%d total=%d cost_micros=%d summary=%s",
                len(accumulator.calls),
                accumulator.grand_total,
                accumulator.total_cost_micros,
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
                        "cost_micros": accumulator.total_cost_micros,
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

        # Finalize premium credit debit with the actual provider cost
        # reported by LiteLLM, summed across every call in the turn.
        # Mirrors the pre-cost behaviour of "premium turn → all calls
        # count" so free sub-agent calls during a premium turn still
        # contribute to the bill (they're $0 in practice anyway).
        if _premium_request_id and user_id:
            try:
                from app.services.token_quota_service import TokenQuotaService

                async with shielded_async_session() as quota_session:
                    await TokenQuotaService.premium_finalize(
                        db_session=quota_session,
                        user_id=UUID(user_id),
                        request_id=_premium_request_id,
                        actual_micros=accumulator.total_cost_micros,
                        reserved_micros=_premium_reserved_micros,
                    )
                _premium_request_id = None
                _premium_reserved_micros = 0
            except Exception:
                logging.getLogger(__name__).warning(
                    "Failed to finalize premium quota for user %s",
                    user_id,
                    exc_info=True,
                )

        usage_summary = accumulator.per_message_summary()
        _perf_log.info(
            "[token_usage] normal new_chat: calls=%d total=%d cost_micros=%d summary=%s",
            len(accumulator.calls),
            accumulator.grand_total,
            accumulator.total_cost_micros,
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
                    "cost_micros": accumulator.total_cost_micros,
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

        # ``BusyError`` fires before the agent acquires the lock; the
        # cleanup path must skip lock release to avoid freeing the
        # in-flight caller's lock. Classification is handled below.
        if isinstance(e, BusyError):
            _busy_error_raised = True

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
            if _premium_request_id and _premium_reserved_micros > 0 and user_id:
                try:
                    from app.services.token_quota_service import TokenQuotaService

                    async with shielded_async_session() as quota_session:
                        await TokenQuotaService.premium_release(
                            db_session=quota_session,
                            user_id=UUID(user_id),
                            reserved_micros=_premium_reserved_micros,
                        )
                    _premium_reserved_micros = 0
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

            # Server-side assistant-message + token_usage finalization.
            # Runs after the main session has been closed (uses its own
            # shielded session) so we don't fight the same DB connection.
            # Idempotent against the legacy frontend appendMessage:
            #  * the assistant row was already INSERTed by
            #    ``persist_assistant_shell`` above, so this just UPDATEs
            #    it with the rich ContentPart[] from the builder.
            #  * token_usage uses INSERT ... ON CONFLICT DO NOTHING
            #    against migration 142's partial unique index, so a
            #    racing append_message recovery branch can never
            #    double-write.
            # ``mark_interrupted`` closes any open text/reasoning blocks
            # and flips running tool-calls (no result) to state=aborted
            # so the persisted JSONB reflects a coherent end-state even
            # on client disconnect.
            # Never raises (best-effort, logs only).
            if (
                stream_result
                and stream_result.turn_id
                and stream_result.assistant_message_id
            ):
                from app.tasks.chat.persistence import finalize_assistant_turn

                builder_stats: dict[str, int] | None = None
                if stream_result.content_builder is not None:
                    stream_result.content_builder.mark_interrupted()
                    # Snapshot stats BEFORE deepcopy in ``snapshot()`` so
                    # the perf log records the actual finalised payload
                    # (post-mark_interrupted), not the live-mutating
                    # builder state.
                    builder_stats = stream_result.content_builder.stats()
                    content_payload = stream_result.content_builder.snapshot()
                else:
                    # Defensive fallback — we always set the builder
                    # alongside ``assistant_message_id`` above, so this
                    # branch only fires if a future refactor ever
                    # decouples them. Persist whatever accumulated
                    # text we captured so the row at least renders.
                    content_payload = [
                        {
                            "type": "text",
                            "text": stream_result.accumulated_text or "",
                        }
                    ]

                if builder_stats is not None:
                    _perf_log.info(
                        "[stream_new_chat] finalize_payload chat_id=%s "
                        "message_id=%s parts=%d bytes=%d text=%d "
                        "reasoning=%d tool_calls=%d "
                        "tool_calls_completed=%d tool_calls_aborted=%d "
                        "thinking_step_parts=%d step_separators=%d",
                        chat_id,
                        stream_result.assistant_message_id,
                        builder_stats["parts"],
                        builder_stats["bytes"],
                        builder_stats["text"],
                        builder_stats["reasoning"],
                        builder_stats["tool_calls"],
                        builder_stats["tool_calls_completed"],
                        builder_stats["tool_calls_aborted"],
                        builder_stats["thinking_step_parts"],
                        builder_stats["step_separators"],
                    )

                await finalize_assistant_turn(
                    message_id=stream_result.assistant_message_id,
                    chat_id=chat_id,
                    search_space_id=search_space_id,
                    user_id=user_id,
                    turn_id=stream_result.turn_id,
                    content=content_payload,
                    accumulator=accumulator,
                )

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

        # ``aafter_agent`` doesn't fire on ``interrupt()`` or early bailout.
        # Skip on ``BusyError`` (caller never acquired the lock).
        if not _busy_error_raised:
            with contextlib.suppress(Exception):
                end_turn(str(chat_id))
                _perf_log.info(
                    "[stream_new_chat] end_turn cleanup (chat_id=%s)",
                    chat_id,
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
    disabled_tools: list[str] | None = None,
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

    # Skip the finally release on ``BusyError`` (caller never acquired the lock).
    _busy_error_raised = False

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

        # Premium credit reservation (same logic as stream_new_chat).
        _resume_premium_reserved_micros = 0
        _resume_premium_request_id: str | None = None
        _resume_needs_premium = (
            agent_config is not None and user_id and agent_config.is_premium
        )
        if _resume_needs_premium:
            import uuid as _uuid

            from app.services.token_quota_service import (
                TokenQuotaService,
                estimate_call_reserve_micros,
            )

            _resume_premium_request_id = _uuid.uuid4().hex[:16]
            _resume_litellm_params = agent_config.litellm_params or {}
            _resume_base_model = (
                _resume_litellm_params.get("base_model")
                or agent_config.model_name
                or ""
            )
            reserve_amount_micros = estimate_call_reserve_micros(
                base_model=_resume_base_model,
                quota_reserve_tokens=agent_config.quota_reserve_tokens,
            )
            async with shielded_async_session() as quota_session:
                quota_result = await TokenQuotaService.premium_reserve(
                    db_session=quota_session,
                    user_id=UUID(user_id),
                    request_id=_resume_premium_request_id,
                    reserve_micros=reserve_amount_micros,
                )
            _resume_premium_reserved_micros = reserve_amount_micros
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
                    _resume_premium_reserved_micros = 0
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

        # Auto-mode preflight ping (resume path). Mirrors ``stream_new_chat``:
        # one cheap probe before the agent is rebuilt so a 429'd pin gets
        # repinned without burning planner/classifier/title calls first.
        # See ``stream_new_chat`` for the full rationale on the speculative
        # parallel build pattern below.
        preflight_needed = (
            requested_llm_config_id == 0
            and llm_config_id < 0
            and not is_recently_healthy(llm_config_id)
        )
        preflight_task: asyncio.Task[None] | None = None
        _t_preflight = 0.0
        if preflight_needed:
            _t_preflight = time.perf_counter()
            preflight_task = asyncio.create_task(
                _preflight_llm(llm),
                name=f"auto_pin_preflight_resume:{llm_config_id}",
            )

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
        from app.config import config as _app_config

        _t0 = time.perf_counter()
        agent_factory = (
            create_multi_agent_chat_deep_agent
            if _app_config.MULTI_AGENT_CHAT_ENABLED
            else create_surfsense_deep_agent
        )
        agent_build_task = asyncio.create_task(
            _build_main_agent_for_thread(
                agent_factory,
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
                disabled_tools=disabled_tools,
            ),
            name="agent_build:stream_resume",
        )

        agent: Any = None
        if preflight_task is not None:
            try:
                await preflight_task
                mark_healthy(llm_config_id)
                _perf_log.info(
                    "[stream_resume] auto_pin_preflight ok config_id=%s took=%.3fs (parallel)",
                    llm_config_id,
                    time.perf_counter() - _t_preflight,
                )
            except Exception as preflight_exc:
                # Same session-safety rationale as ``stream_new_chat``.
                await _settle_speculative_agent_build(agent_build_task)
                if not _is_provider_rate_limited(preflight_exc):
                    raise
                previous_config_id = llm_config_id
                mark_runtime_cooldown(
                    previous_config_id, reason="preflight_rate_limited"
                )
                try:
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
                if llm_load_error or not llm:
                    yield _emit_stream_error(
                        message=llm_load_error or "Failed to create LLM instance",
                        error_kind="server_error",
                        error_code="SERVER_ERROR",
                    )
                    yield streaming_service.format_done()
                    return
                mark_healthy(llm_config_id)
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
                        "Auto-pinned model failed preflight; switched to another "
                        "eligible model and continuing."
                    ),
                    extra={
                        "auto_runtime_recover": True,
                        "preflight": True,
                        "previous_config_id": previous_config_id,
                        "fallback_config_id": llm_config_id,
                    },
                )
                agent = await _build_main_agent_for_thread(
                    agent_factory,
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
                    disabled_tools=disabled_tools,
                )

        if agent is None:
            agent = await agent_build_task
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

        from app.agents.multi_agent_chat.middleware.main_agent.checkpointed_subagent_middleware.resume_routing import (
            collect_pending_tool_calls,
            slice_decisions_by_tool_call,
        )

        # Each pending interrupt is stamped with its originating ``tool_call_id``
        # (see ``checkpointed_subagent_middleware.propagation``) so we can route
        # a flat ``decisions`` list back to the right paused subagent.
        parent_state = await agent.aget_state(
            {"configurable": {"thread_id": str(chat_id)}}
        )
        pending = collect_pending_tool_calls(parent_state)
        _perf_log.info(
            "[hitl_route] resume_entry chat_id=%s decisions=%d pending_subagents=%d",
            chat_id,
            len(decisions),
            len(pending),
        )
        routed_resume_value = slice_decisions_by_tool_call(decisions, pending)

        config = {
            "configurable": {
                "thread_id": str(chat_id),
                "request_id": request_id or "unknown",
                "turn_id": stream_result.turn_id,
                # Per-``tool_call_id`` resume slices read by
                # ``SurfSenseCheckpointedSubAgentMiddleware``. Parallel
                # siblings each pop their own entry, so they never race.
                "surfsense_resume_value": routed_resume_value,
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

        # Pre-write a fresh assistant row for this resume turn. The
        # original (interrupted) ``stream_new_chat`` invocation already
        # persisted its own assistant row anchored to a different
        # ``turn_id``; resume allocates a new ``turn_id`` (above) so we
        # need a separate row keyed on the same ``(thread_id, turn_id,
        # ASSISTANT)`` invariant. Idempotent against migration 141's
        # partial unique index — recovers existing id on retry.
        from app.tasks.chat.content_builder import AssistantContentBuilder
        from app.tasks.chat.persistence import persist_assistant_shell

        assistant_message_id = await persist_assistant_shell(
            chat_id=chat_id,
            user_id=user_id,
            turn_id=stream_result.turn_id,
        )
        if assistant_message_id is None:
            yield _emit_stream_error(
                message=(
                    "We couldn't initialize the assistant message. Please try again."
                ),
                error_kind="server_error",
                error_code="MESSAGE_PERSIST_FAILED",
            )
            yield streaming_service.format_data("turn-status", {"status": "idle"})
            yield streaming_service.format_finish_step()
            yield streaming_service.format_finish()
            yield streaming_service.format_done()
            return

        # Emit canonical assistant message id BEFORE any LLM streaming
        # so the FE can rename ``pendingInterrupt.assistantMsgId`` to
        # ``msg-{assistant_message_id}`` immediately. Resume does NOT
        # emit ``data-user-message-id`` because the user row is from
        # the original interrupted turn (different ``turn_id``) and is
        # never re-persisted here. See B5 in the
        # ``sse-based_message_id_handshake`` plan.
        yield streaming_service.format_data(
            "assistant-message-id",
            {"message_id": assistant_message_id, "turn_id": stream_result.turn_id},
        )

        stream_result.assistant_message_id = assistant_message_id
        stream_result.content_builder = AssistantContentBuilder()

        # Resume path doesn't carry new ``mentioned_document_ids`` —
        # those are seeded in the original turn. We still pass a
        # context so future middleware extensions (Phase 2) can rely on
        # ``runtime.context`` always being populated.
        runtime_context = SurfSenseContextSchema(
            search_space_id=search_space_id,
            request_id=request_id,
            turn_id=stream_result.turn_id,
        )

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
                    runtime_context=runtime_context,
                    content_builder=stream_result.content_builder,
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

                llm, agent_config, llm_load_error = await _load_llm_bundle(
                    llm_config_id
                )
                if llm_load_error:
                    raise stream_exc

                _t0 = time.perf_counter()
                agent = await _build_main_agent_for_thread(
                    agent_factory,
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
                    disabled_tools=disabled_tools,
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
                "[token_usage] interrupted resume_chat: calls=%d total=%d cost_micros=%d summary=%s",
                len(accumulator.calls),
                accumulator.grand_total,
                accumulator.total_cost_micros,
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
                        "cost_micros": accumulator.total_cost_micros,
                        "call_details": accumulator.serialized_calls(),
                    },
                )

            yield streaming_service.format_finish_step()
            yield streaming_service.format_finish()
            yield streaming_service.format_done()
            return

        # Finalize premium credit debit for resume path with the actual
        # provider cost reported by LiteLLM (sum of cost across all
        # calls in the turn).
        if _resume_premium_request_id and user_id:
            try:
                from app.services.token_quota_service import TokenQuotaService

                async with shielded_async_session() as quota_session:
                    await TokenQuotaService.premium_finalize(
                        db_session=quota_session,
                        user_id=UUID(user_id),
                        request_id=_resume_premium_request_id,
                        actual_micros=accumulator.total_cost_micros,
                        reserved_micros=_resume_premium_reserved_micros,
                    )
                _resume_premium_request_id = None
                _resume_premium_reserved_micros = 0
            except Exception:
                logging.getLogger(__name__).warning(
                    "Failed to finalize premium quota for user %s (resume)",
                    user_id,
                    exc_info=True,
                )

        usage_summary = accumulator.per_message_summary()
        _perf_log.info(
            "[token_usage] normal resume_chat: calls=%d total=%d cost_micros=%d summary=%s",
            len(accumulator.calls),
            accumulator.grand_total,
            accumulator.total_cost_micros,
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
                    "cost_micros": accumulator.total_cost_micros,
                    "call_details": accumulator.serialized_calls(),
                },
            )

        yield streaming_service.format_data("turn-status", {"status": "idle"})
        yield streaming_service.format_finish_step()
        yield streaming_service.format_finish()
        yield streaming_service.format_done()

    except Exception as e:
        import traceback

        # ``BusyError`` fires before the agent acquires the lock; the
        # cleanup path must skip lock release to avoid freeing the
        # in-flight caller's lock. Classification is handled below.
        if isinstance(e, BusyError):
            _busy_error_raised = True

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
            if (
                _resume_premium_request_id
                and _resume_premium_reserved_micros > 0
                and user_id
            ):
                try:
                    from app.services.token_quota_service import TokenQuotaService

                    async with shielded_async_session() as quota_session:
                        await TokenQuotaService.premium_release(
                            db_session=quota_session,
                            user_id=UUID(user_id),
                            reserved_micros=_resume_premium_reserved_micros,
                        )
                    _resume_premium_reserved_micros = 0
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

            # Server-side assistant-message + token_usage finalization for
            # the resume flow. The original user message was persisted by
            # the original (interrupted) ``stream_new_chat`` invocation;
            # the resume's own ``persist_assistant_shell`` write lives at
            # the new ``turn_id`` above. This finalize updates that row
            # with the rich ContentPart[] from the builder and writes
            # token_usage idempotently via migration 142's partial
            # unique index. Best-effort, never raises.
            if (
                stream_result
                and stream_result.turn_id
                and stream_result.assistant_message_id
            ):
                from app.tasks.chat.persistence import finalize_assistant_turn

                builder_stats: dict[str, int] | None = None
                if stream_result.content_builder is not None:
                    stream_result.content_builder.mark_interrupted()
                    builder_stats = stream_result.content_builder.stats()
                    content_payload = stream_result.content_builder.snapshot()
                else:
                    content_payload = [
                        {
                            "type": "text",
                            "text": stream_result.accumulated_text or "",
                        }
                    ]

                if builder_stats is not None:
                    _perf_log.info(
                        "[stream_resume] finalize_payload chat_id=%s "
                        "message_id=%s parts=%d bytes=%d text=%d "
                        "reasoning=%d tool_calls=%d "
                        "tool_calls_completed=%d tool_calls_aborted=%d "
                        "thinking_step_parts=%d step_separators=%d",
                        chat_id,
                        stream_result.assistant_message_id,
                        builder_stats["parts"],
                        builder_stats["bytes"],
                        builder_stats["text"],
                        builder_stats["reasoning"],
                        builder_stats["tool_calls"],
                        builder_stats["tool_calls_completed"],
                        builder_stats["tool_calls_aborted"],
                        builder_stats["thinking_step_parts"],
                        builder_stats["step_separators"],
                    )

                await finalize_assistant_turn(
                    message_id=stream_result.assistant_message_id,
                    chat_id=chat_id,
                    search_space_id=search_space_id,
                    user_id=user_id,
                    turn_id=stream_result.turn_id,
                    content=content_payload,
                    accumulator=accumulator,
                )

        # Release the lock from the original interrupted turn or any
        # re-interrupt/bailout. Skip on ``BusyError`` (lock not held here).
        if not _busy_error_raised:
            with contextlib.suppress(Exception):
                end_turn(str(chat_id))
                _perf_log.info(
                    "[stream_resume] end_turn cleanup (chat_id=%s)",
                    chat_id,
                )

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
