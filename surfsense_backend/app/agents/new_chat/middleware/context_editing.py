"""
SpillToBackendEdit + SpillingContextEditingMiddleware.

Mirrors OpenCode's spill-to-disk behavior in
``opencode/packages/opencode/src/tool/truncate.ts``. Before
``ClearToolUsesEdit`` rewrites old ``ToolMessage.content`` to a placeholder,
we capture the full original content and write it to the runtime backend
under ``/tool_outputs/{thread_id}/{message_id}.txt``. The placeholder is
upgraded to ``"[cleared — full output at /tool_outputs/.../{id}.txt; ask the
explore subagent to read it]"`` so the agent can recover it on demand.

Tier 1.2 in the OpenCode-port plan.

Why this is a middleware subclass instead of a plain ``ContextEdit``:
``ContextEdit.apply`` is sync, but writing to the backend is async. We
capture the spill payloads inside ``apply`` and flush them via
``await backend.aupload_files(...)`` from ``awrap_model_call`` *before*
delegating to the handler, so the explore subagent can always read what
the placeholder advertises.
"""

from __future__ import annotations

import logging
import threading
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
    from deepagents.backends.protocol import BackendProtocol
    from langchain.agents.middleware.types import (
        ModelRequest,
        ModelResponse,
    )

logger = logging.getLogger(__name__)

DEFAULT_SPILL_PREFIX = "/tool_outputs"


def _build_spill_placeholder(spill_path: str) -> str:
    """Build the user-facing placeholder text shown to the model."""
    return (
        f"[cleared — full output at {spill_path}; "
        f"ask the explore subagent to read it]"
    )


def _get_thread_id_or_session() -> str:
    """Best-effort thread_id discovery for the spill path.

    Falls back to a process-stable string if no LangGraph config is
    available (e.g. unit tests). The exact value doesn't matter as long
    as it's stable within one stream so the placeholder paths line up
    with the actual upload path.
    """
    try:
        config = get_config()
        thread_id = config.get("configurable", {}).get("thread_id")
        if thread_id is not None:
            return str(thread_id)
    except RuntimeError:
        pass
    return "no_thread"


@dataclass(slots=True)
class SpillToBackendEdit(ContextEdit):
    """Capture-and-replace context edit that spills full tool output to the backend.

    Behaves like :class:`ClearToolUsesEdit` (same trigger / keep / exclude
    semantics) **and** records the original ``ToolMessage.content`` in
    :attr:`pending_spills` so the wrapping middleware can flush them
    before the model call.

    Args:
        trigger: Token threshold above which the edit fires.
        clear_at_least: Minimum number of tokens to reclaim (best effort).
        keep: Number of most-recent ``ToolMessage`` instances to leave
            untouched.
        exclude_tools: Names of tools whose output is NOT spilled.
        clear_tool_inputs: Also clear the originating ``AIMessage.tool_calls``
            args when their pair is cleared.
        path_prefix: Path under the backend where spills are written.
            Default ``"/tool_outputs"``.
    """

    trigger: int = 100_000
    clear_at_least: int = 0
    keep: int = 3
    clear_tool_inputs: bool = False
    exclude_tools: Sequence[str] = ()
    path_prefix: str = DEFAULT_SPILL_PREFIX

    pending_spills: list[tuple[str, bytes]] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def drain_pending(self) -> list[tuple[str, bytes]]:
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
            (idx, msg) for idx, msg in enumerate(messages) if isinstance(msg, ToolMessage)
        ]
        if self.keep >= len(candidates):
            return
        if self.keep:
            candidates = candidates[: -self.keep]

        thread_id = _get_thread_id_or_session()
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

            message_id = tool_message.id or tool_message.tool_call_id or "unknown"
            spill_path = f"{self.path_prefix}/{thread_id}/{message_id}.txt"

            original = tool_message.content
            payload = self._encode_payload(original)
            with self._lock:
                self.pending_spills.append((spill_path, payload))

            messages[idx] = tool_message.model_copy(
                update={
                    "artifact": None,
                    "content": _build_spill_placeholder(spill_path),
                    "response_metadata": {
                        **tool_message.response_metadata,
                        "context_editing": {
                            "cleared": True,
                            "strategy": "spill_to_backend",
                            "spill_path": spill_path,
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


BackendResolver = "Callable[[Any], BackendProtocol] | BackendProtocol"


class SpillingContextEditingMiddleware(ContextEditingMiddleware):
    """:class:`ContextEditingMiddleware` that flushes :class:`SpillToBackendEdit` writes.

    Runs the configured edits as the parent does, then flushes any
    pending spills via the supplied backend resolver before delegating
    to the model handler. Spill failures are logged but never abort the
    model call — the placeholder text is already in the message, so the
    worst case is the agent gets a placeholder it cannot follow up on.
    """

    def __init__(
        self,
        *,
        edits: Sequence[ContextEdit],
        backend_resolver: BackendResolver | None = None,
        token_count_method: str = "approximate",
    ) -> None:
        super().__init__(edits=list(edits), token_count_method=token_count_method)  # type: ignore[arg-type]
        self._backend_resolver = backend_resolver

    def _resolve_backend(self, request: ModelRequest) -> BackendProtocol | None:
        if self._backend_resolver is None:
            return None
        if callable(self._backend_resolver):
            try:
                from langchain.tools import ToolRuntime

                tool_runtime = ToolRuntime(
                    state=getattr(request, "state", {}),
                    context=getattr(request.runtime, "context", None),
                    stream_writer=getattr(request.runtime, "stream_writer", None),
                    store=getattr(request.runtime, "store", None),
                    config=getattr(request.runtime, "config", None) or {},
                    tool_call_id=None,
                )
                return self._backend_resolver(tool_runtime)
            except Exception:
                logger.exception("Failed to resolve spill backend")
                return None
        return self._backend_resolver  # type: ignore[return-value]

    def _collect_pending(self) -> list[tuple[str, bytes]]:
        out: list[tuple[str, bytes]] = []
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
            backend = self._resolve_backend(request)
            if backend is not None:
                try:
                    await backend.aupload_files(pending)
                except Exception:
                    logger.exception(
                        "Spill-to-backend upload failed (%d files); placeholders "
                        "remain in messages but content is unrecoverable",
                        len(pending),
                    )
            else:
                logger.warning(
                    "SpillToBackendEdit produced %d pending spills but no backend "
                    "resolver was configured; content is unrecoverable",
                    len(pending),
                )

        return await handler(request.override(messages=edited_messages))


__all__ = [
    "DEFAULT_SPILL_PREFIX",
    "ClearToolUsesEdit",
    "SpillToBackendEdit",
    "SpillingContextEditingMiddleware",
    "_build_spill_placeholder",
]
