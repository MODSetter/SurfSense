"""Append-only action-log middleware for the SurfSense agent.

Wraps every tool call via :meth:`AgentMiddleware.awrap_tool_call` and writes
a row to :class:`~app.db.AgentActionLog` after the tool returns. Tools opt
into reversibility by declaring a ``reverse`` callable on their
:class:`~app.agents.new_chat.tools.registry.ToolDefinition`; the rendered
descriptor is persisted in ``reverse_descriptor`` for use by
``/api/threads/{thread_id}/revert/{action_id}``.

Design points:

* **Defensive.** Logging never blocks the agent. We catch every exception
  on the DB write path and emit a warning; the tool's ``ToolMessage``
  result is always returned untouched.
* **Lightweight payload.** Only the tool ``name`` + ``args`` (capped) +
  ``result_id`` + ``reverse_descriptor`` are stored. Tool output text
  remains in the LangGraph checkpoint / spilled tool-output files.
* **Best-effort reversibility.** We invoke ``reverse(args, result_obj)``
  with the parsed JSON result when the tool's content is a JSON object;
  otherwise the raw text is passed. Exceptions in the reverse callable
  are swallowed and logged — a failed descriptor render simply means the
  action is NOT marked reversible.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage

from app.agents.new_chat.feature_flags import get_flags
from app.agents.new_chat.tools.registry import ToolDefinition

if TYPE_CHECKING:  # pragma: no cover - type-only
    from langchain.agents.middleware.types import ToolCallRequest
    from langgraph.types import Command


logger = logging.getLogger(__name__)


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
        search_space_id: Search-space id for cascade-on-delete safety.
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
        search_space_id: int,
        user_id: str | None,
        tool_definitions: dict[str, ToolDefinition] | None = None,
    ) -> None:
        super().__init__()
        self._thread_id = thread_id
        self._search_space_id = search_space_id
        self._user_id = user_id
        self._tool_definitions = dict(tool_definitions or {})

    def _enabled(self) -> bool:
        flags = get_flags()
        if flags.disable_new_agent_stack:
            return False
        return bool(flags.enable_action_log) and self._thread_id is not None

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[Any]]],
    ) -> ToolMessage | Command[Any]:
        if not self._enabled():
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
            )
            raise

        await self._record(request=request, result=result, error_payload=None)
        return result

    async def _record(
        self,
        *,
        request: ToolCallRequest,
        result: ToolMessage | Command[Any] | None,
        error_payload: dict[str, Any] | None,
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

            row = AgentActionLog(
                thread_id=self._thread_id,
                user_id=self._user_id,
                search_space_id=self._search_space_id,
                turn_id=_resolve_turn_id(request),
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
        except Exception:
            logger.warning(
                "ActionLogMiddleware failed to persist action log row",
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


def _resolve_turn_id(request: Any) -> str | None:
    try:
        call = getattr(request, "tool_call", None) or {}
        if isinstance(call, dict):
            tid = call.get("id")
            if isinstance(tid, str):
                return tid
    except Exception:  # pragma: no cover
        pass
    return None


def _resolve_message_id(request: Any) -> str | None:
    """Tool-call IDs serve as best-available message correlator at this layer."""
    return _resolve_turn_id(request)


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
