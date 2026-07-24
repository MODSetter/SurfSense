"""Append-only action-log middleware for the SurfSense agent.

Wraps every tool call and writes a row to :class:`~app.db.AgentActionLog`
after the tool returns. Tools opt into reversibility via a ``reverse``
callable on their :class:`ToolDefinition`; the rendered descriptor powers
``/api/threads/{thread_id}/revert/{action_id}``.

Logging is fully defensive — DB-write failures are swallowed so the tool's
result is always returned untouched. Only metadata (name, capped args,
result_id, reverse_descriptor) is stored; tool output stays in the
checkpoint. Reversibility is best-effort: a reverse callable that raises
just leaves the action non-reversible.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from langchain.agents.middleware import AgentMiddleware
from langchain_core.callbacks import adispatch_custom_event
from langchain_core.messages import ToolMessage

from app.agents.chat.multi_agent_chat.shared.feature_flags import get_flags

if TYPE_CHECKING:  # pragma: no cover - type-only
    from langchain.agents.middleware.types import ToolCallRequest
    from langgraph.types import Command


logger = logging.getLogger(__name__)


@dataclass
class ToolDefinition:
    """Reversibility descriptor consumed by :class:`ActionLogMiddleware`.

    Only ``name`` and ``reverse`` are read by the middleware; the remaining
    fields let callers and tests describe a tool declaratively. A tool is
    marked reversible in the action log when ``reverse`` is set and renders a
    descriptor without raising.

    Attributes:
        name: Unique identifier for the tool.
        description: Human-readable description of what the tool does.
        factory: Optional callable that builds the tool (unused by the
            middleware; retained for declarative call sites/tests).
        reverse: Optional callable that, given the tool's ``(args, result)``,
            returns a ``ReverseDescriptor`` describing the inverse invocation.

    """

    name: str
    description: str = ""
    factory: Callable[[dict[str, Any]], Any] | None = None
    reverse: Callable[[dict[str, Any], Any], dict[str, Any]] | None = None


# Cap for the persisted ``args`` JSON to avoid bloating the action log with
# accidentally-huge inputs. Values are truncated and a flag is set in the
# stored payload so consumers can detect truncation.
_MAX_ARGS_PERSIST_BYTES = 32 * 1024  # 32KB


class ActionLogMiddleware(AgentMiddleware):
    """Persist a row in :class:`AgentActionLog` after every tool call.

    Should be placed near the OUTERMOST end of the tool-call wrapping stack
    so that it sees the *final* :class:`ToolMessage` after all retries,
    permission checks, and dedup logic have run. In practice that means
    placing it just inside :class:`PermissionMiddleware` and outside
    :class:`DedupHITLToolCallsMiddleware`.

    The middleware is fully a no-op when:

    * the master kill-switch ``SURFSENSE_DISABLE_NEW_AGENT_STACK`` is set
      (checked via :func:`get_flags`),
    * the per-feature flag ``enable_action_log`` is off, or
    * persistence raises (defensive: tool-call dispatch always succeeds).

    Args:
        thread_id: The current chat thread's primary-key id. Required to
            persist a row; if ``None`` the middleware silently no-ops.
        workspace_id: Workspace id for cascade-on-delete safety.
        user_id: UUID string of the user driving this turn (nullable in
            anonymous mode).
        tool_definitions: Optional mapping of tool name -> :class:`ToolDefinition`
            so the middleware can look up the tool's ``reverse`` callable.
            When omitted, no actions are marked reversible.
    """

    tools = ()

    def __init__(
        self,
        *,
        thread_id: int | None,
        workspace_id: int,
        user_id: str | None,
        tool_definitions: dict[str, ToolDefinition] | None = None,
    ) -> None:
        super().__init__()
        self._thread_id = thread_id
        self._workspace_id = workspace_id
        self._user_id = user_id
        self._tool_definitions = dict(tool_definitions or {})

    def _enabled(self, thread_id: int | None) -> bool:
        flags = get_flags()
        if flags.disable_new_agent_stack:
            return False
        return bool(flags.enable_action_log) and thread_id is not None

    def _resolve_thread_id(self, request: ToolCallRequest) -> int | None:
        """Resolve the live thread id, preferring the runtime config.

        Reading ``configurable.thread_id`` from the active ``RunnableConfig``
        (rather than the value captured at ``__init__``) lets a single cached
        compiled graph safely serve many threads — without it, a cache hit
        would attribute action-log rows to whichever thread first built the
        graph. Falls back to the constructor value for legacy/test runtimes
        that don't surface a config.
        """
        resolved = _resolve_thread_id(request)
        return resolved if resolved is not None else self._thread_id

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[Any]]],
    ) -> ToolMessage | Command[Any]:
        thread_id = self._resolve_thread_id(request)
        if not self._enabled(thread_id):
            return await handler(request)

        result: ToolMessage | Command[Any]
        error_payload: dict[str, Any] | None = None
        try:
            result = await handler(request)
        except Exception as exc:
            # Persist the failure too so revert/audit can see it, then
            # re-raise so downstream middleware (RetryAfter, etc.) handles it.
            error_payload = {"type": type(exc).__name__, "message": str(exc)}
            await self._record(
                request=request,
                result=None,
                error_payload=error_payload,
                thread_id=thread_id,
            )
            raise

        await self._record(
            request=request,
            result=result,
            error_payload=None,
            thread_id=thread_id,
        )
        return result

    async def _record(
        self,
        *,
        request: ToolCallRequest,
        result: ToolMessage | Command[Any] | None,
        error_payload: dict[str, Any] | None,
        thread_id: int | None,
    ) -> None:
        """Persist one ``agent_action_log`` row. Defensive: never raises."""
        try:
            from app.db import AgentActionLog, shielded_async_session

            tool_name = _resolve_tool_name(request)
            args_payload = _resolve_args_payload(request)
            result_id = _resolve_result_id(result)
            reverse_descriptor, reversible = self._render_reverse(
                tool_name=tool_name,
                args=_resolve_args_dict(request),
                result=result,
            )

            tool_call_id = _resolve_tool_call_id(request)
            chat_turn_id = _resolve_chat_turn_id(request)

            row = AgentActionLog(
                thread_id=thread_id,
                user_id=self._user_id,
                workspace_id=self._workspace_id,
                # ``turn_id`` is the deprecated alias of ``tool_call_id``
                # kept for one release for safe rollback. New consumers
                # should read ``tool_call_id`` directly.
                turn_id=tool_call_id,
                tool_call_id=tool_call_id,
                chat_turn_id=chat_turn_id,
                message_id=_resolve_message_id(request),
                tool_name=tool_name,
                args=args_payload,
                result_id=result_id,
                reversible=reversible,
                reverse_descriptor=reverse_descriptor,
                error=error_payload,
            )
            async with shielded_async_session() as session:
                session.add(row)
                await session.commit()
                row_id = int(row.id) if row.id is not None else None
                row_created_at = row.created_at
        except Exception:
            logger.warning(
                "ActionLogMiddleware failed to persist action log row",
                exc_info=True,
            )
            return

        # Side-channel event (relayed by ``stream_new_chat`` as a
        # ``data-action-log`` SSE) so the tool card can show a Revert button
        # once the row is durable. Carries a presence flag, not the descriptor.
        try:
            await adispatch_custom_event(
                "action_log",
                {
                    "id": row_id,
                    "lc_tool_call_id": tool_call_id,
                    "chat_turn_id": chat_turn_id,
                    "tool_name": tool_name,
                    "reversible": bool(reversible),
                    "reverse_descriptor_present": reverse_descriptor is not None,
                    "created_at": row_created_at.isoformat()
                    if row_created_at
                    else None,
                    "error": error_payload is not None,
                },
            )
        except Exception:
            logger.debug(
                "ActionLogMiddleware failed to dispatch action_log event",
                exc_info=True,
            )

    def _render_reverse(
        self,
        *,
        tool_name: str,
        args: dict[str, Any] | None,
        result: ToolMessage | Command[Any] | None,
    ) -> tuple[dict[str, Any] | None, bool]:
        """Run the tool's ``reverse`` callable and return its descriptor.

        Returns a tuple of ``(descriptor_or_None, reversible_bool)``. When
        the tool has no ``reverse`` callable, or when the callable raises,
        the action is marked non-reversible.
        """
        if not result or not isinstance(result, ToolMessage):
            return None, False
        if args is None:
            return None, False
        tool_def = self._tool_definitions.get(tool_name)
        if tool_def is None or tool_def.reverse is None:
            return None, False
        try:
            parsed_result = _parse_tool_result_content(result)
            descriptor = tool_def.reverse(args, parsed_result)
        except Exception:
            logger.warning(
                "Reverse descriptor render failed for tool %s",
                tool_name,
                exc_info=True,
            )
            return None, False
        if not isinstance(descriptor, dict):
            return None, False
        return descriptor, True


# ---------------------------------------------------------------------------
# Resolution helpers — defensive against tool_call request shape variation.
# ---------------------------------------------------------------------------


def _resolve_tool_name(request: Any) -> str:
    try:
        tool = getattr(request, "tool", None)
        if tool is not None:
            name = getattr(tool, "name", None)
            if isinstance(name, str) and name:
                return name
        call = getattr(request, "tool_call", None) or {}
        if isinstance(call, dict):
            name = call.get("name")
            if isinstance(name, str) and name:
                return name
    except Exception:  # pragma: no cover - defensive
        pass
    return "unknown"


def _resolve_args_dict(request: Any) -> dict[str, Any] | None:
    try:
        call = getattr(request, "tool_call", None)
        if not isinstance(call, dict):
            return None
        args = call.get("args")
        if isinstance(args, dict):
            return args
        return None
    except Exception:  # pragma: no cover - defensive
        return None


def _resolve_args_payload(request: Any) -> dict[str, Any] | None:
    """Return a JSON-serializable args dict, truncated if too big."""
    args = _resolve_args_dict(request)
    if args is None:
        return None
    try:
        encoded = json.dumps(args, default=str)
    except Exception:
        return {"_repr": repr(args)[:_MAX_ARGS_PERSIST_BYTES]}
    if len(encoded) <= _MAX_ARGS_PERSIST_BYTES:
        return args
    return {
        "_truncated": True,
        "_size": len(encoded),
        "_preview": encoded[:_MAX_ARGS_PERSIST_BYTES],
    }


def _resolve_tool_call_id(request: Any) -> str | None:
    """Return the LangChain ``tool_call.id`` for this request, if any."""
    try:
        call = getattr(request, "tool_call", None) or {}
        if isinstance(call, dict):
            tid = call.get("id")
            if isinstance(tid, str):
                return tid
    except Exception:  # pragma: no cover
        pass
    return None


# Deprecated alias kept for one release. Old callers and tests treated
# ``turn_id`` as if it carried the LangChain tool_call id; the new column
# lives under ``tool_call_id``. Both resolve to the same value today.
_resolve_turn_id = _resolve_tool_call_id


def _resolve_chat_turn_id(request: Any) -> str | None:
    """Return ``configurable.turn_id`` for this request, if accessible.

    ``ToolRuntime.config`` is exposed by LangGraph (see
    ``langgraph/prebuilt/tool_node.py``); the chat-turn correlation id
    lives at ``runtime.config["configurable"]["turn_id"]``.
    """
    try:
        runtime = getattr(request, "runtime", None)
        if runtime is None:
            return None
        config = getattr(runtime, "config", None)
        if not isinstance(config, dict):
            return None
        configurable = config.get("configurable")
        if not isinstance(configurable, dict):
            return None
        value = configurable.get("turn_id")
        if isinstance(value, str) and value:
            return value
    except Exception:  # pragma: no cover - defensive
        pass
    return None


def _resolve_thread_id(request: Any) -> int | None:
    """Return ``configurable.thread_id`` (as int) for this request, if accessible.

    Mirrors :func:`_resolve_chat_turn_id`: ``ToolRuntime.config`` is exposed by
    LangGraph at ``request.runtime.config``, and the chat thread id lives at
    ``configurable.thread_id`` (a stringified ``chat_id`` at the main-graph
    level). Returns ``None`` when absent or unparseable so the caller can fall
    back to the constructor value.
    """
    try:
        runtime = getattr(request, "runtime", None)
        if runtime is None:
            return None
        config = getattr(runtime, "config", None)
        if not isinstance(config, dict):
            return None
        configurable = config.get("configurable")
        if not isinstance(configurable, dict):
            return None
        value = configurable.get("thread_id")
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
    except Exception:  # pragma: no cover - defensive
        return None


def _resolve_message_id(request: Any) -> str | None:
    """Tool-call IDs serve as best-available message correlator at this layer."""
    return _resolve_tool_call_id(request)


def _resolve_result_id(result: Any) -> str | None:
    if isinstance(result, ToolMessage):
        msg_id = getattr(result, "id", None)
        if isinstance(msg_id, str):
            return msg_id
    return None


def _parse_tool_result_content(result: ToolMessage) -> Any:
    content = result.content
    if isinstance(content, str):
        try:
            return json.loads(content)
        except (json.JSONDecodeError, ValueError):
            return content
    return content


__all__ = ["ActionLogMiddleware"]
