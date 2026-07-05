"""Server-side assistant-message + token_usage finalization.

Runs inside the streaming flow's ``finally`` block, after the main session has
been closed (uses its own shielded session, so we don't fight the same DB
connection).

Idempotent against the legacy frontend ``appendMessage`` recovery branch:

  * the assistant row was already INSERTed by ``persist_assistant_shell``
    earlier in the turn, so this just UPDATEs it with the rich
    ``ContentPart[]`` projection from the builder.
  * ``token_usage`` uses ``INSERT ... ON CONFLICT DO NOTHING`` against the
    partial unique index from migration 142, so a racing append_message
    recovery branch can never double-write.

``mark_interrupted`` closes any open text/reasoning blocks and flips running
tool-calls (no result) to ``state=aborted`` so the persisted JSONB reflects a
coherent end-state even on client disconnect.

Never raises (best-effort, logs only).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.agents.chat.multi_agent_chat.shared.citations import (
    CitationRegistry,
    normalize_citations,
)
from app.tasks.chat.streaming.shared.stream_result import StreamResult
from app.utils.perf import get_perf_logger

if TYPE_CHECKING:
    from app.services.token_tracking_service import TokenAccumulator

_perf_log = get_perf_logger()


def _as_registry(raw: Any) -> CitationRegistry | None:
    """Coerce the captured state value into a registry, tolerating a serialized dict."""
    if isinstance(raw, CitationRegistry):
        return raw
    if isinstance(raw, dict):
        try:
            return CitationRegistry.model_validate(raw)
        except Exception:
            return None
    return None


def _resolve_citations(
    content_payload: list[dict[str, Any]], raw_registry: Any
) -> list[dict[str, Any]]:
    """Rewrite ``[n]`` -> ``[citation:<payload>]`` in each text part before persisting.

    No-op when the turn registered no citable sources; any pre-existing
    ``[citation:url]`` markers pass through untouched (the regex matches bare ``[n]``).
    """
    registry = _as_registry(raw_registry)
    if registry is None or not registry.by_n:
        return content_payload
    for part in content_payload:
        if part.get("type") == "text" and isinstance(part.get("text"), str):
            part["text"] = normalize_citations(part["text"], registry)
    return content_payload


async def finalize_assistant_message(
    *,
    stream_result: StreamResult | None,
    chat_id: int,
    workspace_id: int,
    user_id: str | None,
    accumulator: TokenAccumulator,
    log_prefix: str,
) -> None:
    """Snapshot the content builder and persist the final assistant payload.

    No-op when ``stream_result`` was never populated, the turn never reached
    ``persist_assistant_shell`` (no ``assistant_message_id``), or the turn id
    was never assigned.
    """
    if not (
        stream_result and stream_result.turn_id and stream_result.assistant_message_id
    ):
        return

    from app.tasks.chat.message_parts_normalizer import merge_streamed_and_final_parts
    from app.tasks.chat.persistence import finalize_assistant_turn

    builder_stats: dict[str, int] | None = None
    if stream_result.content_builder is not None:
        stream_result.content_builder.mark_interrupted()
        # Snapshot stats BEFORE ``snapshot()`` deepcopies so the perf log
        # records the actual finalised payload (post-mark_interrupted), not
        # the live-mutating builder state.
        builder_stats = stream_result.content_builder.stats()
        content_payload = stream_result.content_builder.snapshot()
    else:
        # Defensive fallback — we always set the builder alongside
        # ``assistant_message_id`` in the orchestrator, so this branch only
        # fires if a future refactor ever decouples them. Persist whatever
        # accumulated text we captured so the row at least renders.
        content_payload = [
            {
                "type": "text",
                "text": stream_result.accumulated_text or "",
            }
        ]
    content_payload = merge_streamed_and_final_parts(
        content_payload,
        stream_result.final_message_parts,
    )
    content_payload = _resolve_citations(
        content_payload, stream_result.citation_registry
    )

    if builder_stats is not None:
        _perf_log.info(
            "[%s] finalize_payload chat_id=%s "
            "message_id=%s parts=%d bytes=%d text=%d "
            "reasoning=%d tool_calls=%d "
            "tool_calls_completed=%d tool_calls_aborted=%d "
            "thinking_step_parts=%d step_separators=%d",
            log_prefix,
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
        workspace_id=workspace_id,
        user_id=user_id,
        turn_id=stream_result.turn_id,
        content=content_payload,
        accumulator=accumulator,
    )
