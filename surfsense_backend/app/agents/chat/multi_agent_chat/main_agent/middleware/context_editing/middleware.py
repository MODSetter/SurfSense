"""
SpillToBackendEdit + SpillingContextEditingMiddleware.

LangChain's :class:`ClearToolUsesEdit` discards old ``ToolMessage.content``
when the context-editing budget triggers, replacing the body with a fixed
placeholder. That's lossy: anything the agent might want to revisit is
gone. The spill pattern (originally from OpenCode's
``opencode/packages/opencode/src/tool/truncate.ts``) keeps the prune
behavior but persists the full original payload first — to the
``tool_output_spills`` table — and upgrades the placeholder to a
``spill_<uuid>`` reference the agent can read back with the shared
``read_run``/``search_run`` tools on demand.

Why the DB and not the runtime filesystem backend: the previous version
wrote via ``backend.aupload_files``, which is a no-op on cloud
(``KBPostgresBackend`` raises ``NotImplementedError``) and mismatched on
desktop (paths must be ``/{mount_id}/...``), so spills were unrecoverable
in production. A table works on every deployment and needs no sandbox.

Why this is a middleware subclass instead of a plain ``ContextEdit``:
``ContextEdit.apply`` is sync, but the DB write is async. We generate the
spill id and capture the payload inside ``apply`` (so the placeholder can
reference the final id immediately) and flush the rows from
``awrap_model_call`` *before* delegating to the handler.
"""

from __future__ import annotations

import logging
import threading
import uuid
from collections.abc import Awaitable, Callable, Sequence
from copy import deepcopy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from langchain.agents.middleware.context_editing import (
    ClearToolUsesEdit,
    ContextEdit,
    ContextEditingMiddleware,
    TokenCounter,
)
from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    BaseMessage,
    ToolMessage,
)
from langchain_core.messages.utils import count_tokens_approximately
from langgraph.config import get_config

if TYPE_CHECKING:
    from langchain.agents.middleware.types import (
        ModelRequest,
        ModelResponse,
    )

logger = logging.getLogger(__name__)

# Namespace for deterministic spill ids: the same (thread, message) always maps
# to the same row, so re-running the edit on later model calls (edits apply to a
# per-call copy of the messages, never to persisted state) re-references the
# existing spill instead of inserting a duplicate every turn.
_SPILL_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


def _spill_id_for(thread_id: str | None, message_key: str) -> uuid.UUID:
    return uuid.uuid5(_SPILL_NAMESPACE, f"{thread_id or 'no_thread'}:{message_key}")


def _build_spill_placeholder(spill_id: uuid.UUID) -> str:
    """Build the user-facing placeholder text shown to the model."""
    return (
        f"[cleared — full output stored as spill_{spill_id}; "
        "use read_run/search_run to read it]"
    )


def _get_thread_id() -> str | None:
    """Best-effort ``configurable.thread_id`` for the spill row (``None`` if absent)."""
    try:
        config = get_config()
        thread_id = config.get("configurable", {}).get("thread_id")
        if thread_id is not None:
            return str(thread_id)
    except RuntimeError:
        pass
    return None


@dataclass(slots=True)
class SpillToBackendEdit(ContextEdit):
    """Capture-and-replace context edit that spills full tool output to the DB.

    Behaves like :class:`ClearToolUsesEdit` (same trigger / keep / exclude
    semantics) **and** records the original ``ToolMessage.content`` in
    :attr:`pending_spills` so the wrapping middleware can flush the rows to
    ``tool_output_spills`` before the model call. The spill id is generated up
    front so the placeholder can reference it immediately.

    Args:
        trigger: Token threshold above which the edit fires.
        clear_at_least: Minimum number of tokens to reclaim (best effort).
        keep: Number of most-recent ``ToolMessage`` instances to leave
            untouched.
        exclude_tools: Names of tools whose output is NOT spilled.
        clear_tool_inputs: Also clear the originating ``AIMessage.tool_calls``
            args when their pair is cleared.
    """

    trigger: int = 100_000
    clear_at_least: int = 0
    keep: int = 3
    clear_tool_inputs: bool = False
    exclude_tools: Sequence[str] = ()

    # (spill_id, content_bytes, tool_name, thread_id)
    pending_spills: list[tuple[uuid.UUID, bytes, str | None, str | None]] = field(
        default_factory=list
    )
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def drain_pending(
        self,
    ) -> list[tuple[uuid.UUID, bytes, str | None, str | None]]:
        """Return and clear the pending-spill list atomically."""
        with self._lock:
            out = list(self.pending_spills)
            self.pending_spills.clear()
        return out

    def apply(
        self,
        messages: list[AnyMessage],
        *,
        count_tokens: TokenCounter,
    ) -> None:
        """Mirror ``ClearToolUsesEdit.apply`` but capture originals first."""
        tokens = count_tokens(messages)
        if tokens <= self.trigger:
            return

        candidates = [
            (idx, msg)
            for idx, msg in enumerate(messages)
            if isinstance(msg, ToolMessage)
        ]
        if self.keep >= len(candidates):
            return
        if self.keep:
            candidates = candidates[: -self.keep]

        thread_id = _get_thread_id()
        excluded_tools = set(self.exclude_tools)

        for idx, tool_message in candidates:
            if tool_message.response_metadata.get("context_editing", {}).get("cleared"):
                continue

            ai_message = next(
                (m for m in reversed(messages[:idx]) if isinstance(m, AIMessage)),
                None,
            )
            if ai_message is None:
                continue

            tool_call = next(
                (
                    call
                    for call in ai_message.tool_calls
                    if call.get("id") == tool_message.tool_call_id
                ),
                None,
            )
            if tool_call is None:
                continue

            tool_name = tool_message.name or tool_call["name"]
            if tool_name in excluded_tools:
                continue

            message_key = tool_message.id or tool_message.tool_call_id or "unknown"
            spill_id = _spill_id_for(thread_id, message_key)
            original = tool_message.content
            payload = self._encode_payload(original)
            with self._lock:
                self.pending_spills.append((spill_id, payload, tool_name, thread_id))

            messages[idx] = tool_message.model_copy(
                update={
                    "artifact": None,
                    "content": _build_spill_placeholder(spill_id),
                    "response_metadata": {
                        **tool_message.response_metadata,
                        "context_editing": {
                            "cleared": True,
                            "strategy": "spill_to_db",
                            "spill_id": str(spill_id),
                        },
                    },
                }
            )

            if self.clear_tool_inputs:
                ai_idx = messages.index(ai_message)
                messages[ai_idx] = self._clear_input_args(
                    ai_message, tool_message.tool_call_id or ""
                )

            if self.clear_at_least > 0:
                new_token_count = count_tokens(messages)
                cleared_tokens = max(0, tokens - new_token_count)
                if cleared_tokens >= self.clear_at_least:
                    break

    @staticmethod
    def _encode_payload(content: Any) -> bytes:
        """Serialize ``ToolMessage.content`` to bytes for upload."""
        if isinstance(content, bytes):
            return content
        if isinstance(content, str):
            return content.encode("utf-8")
        try:
            import json

            return json.dumps(content, default=str).encode("utf-8")
        except Exception:
            return str(content).encode("utf-8")

    @staticmethod
    def _clear_input_args(message: AIMessage, tool_call_id: str) -> AIMessage:
        updated_tool_calls: list[dict[str, Any]] = []
        cleared_any = False
        for tool_call in message.tool_calls:
            updated = dict(tool_call)
            if updated.get("id") == tool_call_id:
                updated["args"] = {}
                cleared_any = True
            updated_tool_calls.append(updated)

        metadata = dict(getattr(message, "response_metadata", {}))
        if cleared_any:
            ctx = dict(metadata.get("context_editing", {}))
            ids = set(ctx.get("cleared_tool_inputs", []))
            ids.add(tool_call_id)
            ctx["cleared_tool_inputs"] = sorted(ids)
            metadata["context_editing"] = ctx
        return message.model_copy(
            update={
                "tool_calls": updated_tool_calls,
                "response_metadata": metadata,
            }
        )


class SpillingContextEditingMiddleware(ContextEditingMiddleware):
    """:class:`ContextEditingMiddleware` that flushes :class:`SpillToBackendEdit` writes.

    Runs the configured edits as the parent does, then persists any pending
    spills to ``tool_output_spills`` before delegating to the model handler.
    Spill failures are logged but never abort the model call — the placeholder
    text is already in the message, so the worst case is the agent gets a
    placeholder it cannot follow up on.
    """

    def __init__(
        self,
        *,
        edits: Sequence[ContextEdit],
        workspace_id: int | None = None,
        token_count_method: str = "approximate",
    ) -> None:
        super().__init__(edits=list(edits), token_count_method=token_count_method)  # type: ignore[arg-type]
        self._workspace_id = workspace_id

    def _collect_pending(
        self,
    ) -> list[tuple[uuid.UUID, bytes, str | None, str | None]]:
        out: list[tuple[uuid.UUID, bytes, str | None, str | None]] = []
        for edit in self.edits:
            if isinstance(edit, SpillToBackendEdit):
                out.extend(edit.drain_pending())
        return out

    async def awrap_model_call(  # type: ignore[override]
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> Any:
        if not request.messages:
            return await handler(request)

        if self.token_count_method == "approximate":

            def count_tokens(messages: Sequence[BaseMessage]) -> int:
                return count_tokens_approximately(messages)

        else:
            system_msg = [request.system_message] if request.system_message else []

            def count_tokens(messages: Sequence[BaseMessage]) -> int:
                return request.model.get_num_tokens_from_messages(
                    system_msg + list(messages), request.tools
                )

        edited_messages = deepcopy(list(request.messages))
        for edit in self.edits:
            edit.apply(edited_messages, count_tokens=count_tokens)

        pending = self._collect_pending()
        if pending:
            await self._flush_spills(pending)

        return await handler(request.override(messages=edited_messages))

    async def _flush_spills(
        self, pending: list[tuple[uuid.UUID, bytes, str | None, str | None]]
    ) -> None:
        """Persist spilled tool outputs to the DB (best-effort)."""
        from app.capabilities.core.runs import record_spill
        from app.db import async_session_maker

        try:
            async with async_session_maker() as session:
                for spill_id, payload, tool_name, thread_id in pending:
                    await record_spill(
                        session,
                        spill_id=spill_id,
                        content=payload.decode("utf-8", errors="replace"),
                        workspace_id=self._workspace_id,
                        thread_id=thread_id,
                        tool_name=tool_name,
                    )
        except Exception:
            logger.exception(
                "Spill-to-DB flush failed (%d rows); placeholders remain in "
                "messages but content is unrecoverable",
                len(pending),
            )


__all__ = [
    "ClearToolUsesEdit",
    "SpillToBackendEdit",
    "SpillingContextEditingMiddleware",
    "_build_spill_placeholder",
]
