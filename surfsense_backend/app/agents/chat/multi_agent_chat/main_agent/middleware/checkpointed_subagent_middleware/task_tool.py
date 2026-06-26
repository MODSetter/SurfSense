"""Build the ``task`` tool that invokes subagents with HITL bridging.

The tool's body is the only place where the parent and the subagent meet at
runtime: it reads the parent's stashed resume value, decides whether to send
fresh state or a targeted ``Command(resume=...)`` to the subagent, then
re-raises any new pending interrupt back to the parent.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Annotated, Any, NoReturn, TypeVar

from deepagents.middleware.subagents import TASK_TOOL_DESCRIPTION
from langchain.tools import BaseTool, ToolRuntime
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.runnables import Runnable
from langchain_core.tools import StructuredTool
from langgraph.errors import GraphInterrupt
from langgraph.types import Command, Interrupt

from app.agents.chat.multi_agent_chat.subagents.shared.invocation import (
    EXCLUDED_STATE_KEYS,
    subagent_invoke_config,
)
from app.agents.chat.multi_agent_chat.subagents.shared.spec import (
    SURF_CONTEXT_HINT_PROVIDER_KEY,
    ContextHintProvider,
)
from app.observability import metrics as ot_metrics, otel as ot
from app.utils.perf import get_perf_logger

from .config import (
    consume_surfsense_resume,
    drain_parent_null_resume,
    has_surfsense_resume,
)
from .constants import (
    DEFAULT_SUBAGENT_BATCH_CONCURRENCY,
    DEFAULT_SUBAGENT_BILLABLE_THRESHOLD,
    DEFAULT_SUBAGENT_INVOKE_TIMEOUT_SECONDS,
    MAX_SUBAGENT_BATCH_SIZE,
)
from .propagation import wrap_with_tool_call_id
from .resume import (
    build_resume_command,
    fan_out_decisions_to_match,
    get_first_pending_subagent_interrupt,
    hitlrequest_action_count,
)
from .spawn_paused import is_spawn_paused

logger = logging.getLogger(__name__)
_perf_log = get_perf_logger()


class SubagentInvokeTimeoutError(Exception):
    """Raised when ``subagent.ainvoke`` exceeds the configured wall-clock budget.

    Carries the subagent name and the elapsed seconds so the caller can
    synthesize a ToolMessage that the orchestrator can act on (re-route,
    surface to the user, or retry with a smaller scope).
    """

    def __init__(self, subagent_type: str, elapsed_seconds: float) -> None:
        super().__init__(
            f"subagent {subagent_type!r} exceeded "
            f"{DEFAULT_SUBAGENT_INVOKE_TIMEOUT_SECONDS:.0f}s budget "
            f"(elapsed={elapsed_seconds:.1f}s)"
        )
        self.subagent_type = subagent_type
        self.elapsed_seconds = elapsed_seconds


_T = TypeVar("_T")


async def _ainvoke_with_timeout[T](
    coro: Awaitable[_T], *, subagent_type: str, started_at: float
) -> _T:
    """Apply the subagent invoke timeout to ``coro`` (non-positive disables it).

    On expiry the task is cancelled and :class:`SubagentInvokeTimeoutError` is
    raised for the caller to turn into a synthetic ToolMessage.
    """
    timeout = DEFAULT_SUBAGENT_INVOKE_TIMEOUT_SECONDS
    if timeout <= 0:
        return await coro
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except TimeoutError as exc:
        elapsed = time.perf_counter() - started_at
        raise SubagentInvokeTimeoutError(subagent_type, elapsed) from exc


def _synthesize_timeout_command(
    exc: SubagentInvokeTimeoutError, *, tool_call_id: str
) -> Command:
    """Turn a :class:`SubagentInvokeTimeoutError` into a ToolMessage the parent can read."""
    content = (
        f"Subagent {exc.subagent_type!r} timed out after "
        f"{exc.elapsed_seconds:.1f}s (budget="
        f"{DEFAULT_SUBAGENT_INVOKE_TIMEOUT_SECONDS:.0f}s). "
        "The work was cancelled. Treat as status=error; re-route with a "
        "narrower scope or different specialist."
    )
    return Command(
        update={"messages": [ToolMessage(content=content, tool_call_id=tool_call_id)]}
    )


def _reraise_stamped_subagent_interrupt(
    gi: GraphInterrupt, tool_call_id: str
) -> NoReturn:
    """Stamp ``tool_call_id`` onto each pending interrupt value and re-raise.

    See :mod:`...propagation` for why this stamp is required for resume routing.
    Chained via ``from gi`` so tracebacks point at the subagent's original
    ``interrupt(...)`` site.
    """
    interrupts = gi.args[0] if gi.args else ()
    stamped = tuple(
        Interrupt(
            value=wrap_with_tool_call_id(i.value, tool_call_id),
            id=i.id,
        )
        for i in interrupts
    )
    logger.info(
        "[hitl_route] stamped %d subagent interrupt(s) with tool_call_id=%s",
        len(stamped),
        tool_call_id,
    )
    raise GraphInterrupt(stamped) from gi


def build_task_tool_with_parent_config(
    subagents: list[dict[str, Any]],
    task_description: str | None = None,
    *,
    search_space_id: int | None = None,
    resolve_subagent: Callable[[str], Runnable] | None = None,
) -> BaseTool:
    """Upstream ``_build_task_tool`` + parent ``runtime.config`` propagation + resume bridging.

    ``subagents`` are lightweight descriptors (``name``/``description`` + the
    optional context-hint provider); the actual compiled graph is fetched
    lazily via ``resolve_subagent(name)`` so subagent ``create_agent`` cost is
    paid on first ``task(name)`` use rather than at graph-build time.

    For backward compatibility (and tests), ``resolve_subagent`` may be omitted
    when every descriptor already carries a pre-compiled ``runnable``; in that
    case a trivial dict-backed resolver is used.
    """
    subagent_names: set[str] = {spec["name"] for spec in subagents}
    if resolve_subagent is None:
        _eager_graphs: dict[str, Runnable] = {
            spec["name"]: spec["runnable"] for spec in subagents if "runnable" in spec
        }

        def resolve_subagent(name: str) -> Runnable:
            return _eager_graphs[name]

    # Sparse map of opt-in context-hint providers; each runs once per task()
    # call to prepend a string to the subagent's first HumanMessage. Failures
    # are swallowed so a broken hint never blocks the task.
    subagent_hint_providers: dict[str, ContextHintProvider] = {
        spec["name"]: provider
        for spec in subagents
        if (provider := spec.get(SURF_CONTEXT_HINT_PROVIDER_KEY)) is not None
    }
    subagent_description_str = "\n".join(
        f"- {s['name']}: {s['description']}" for s in subagents
    )

    if task_description is None:
        description = TASK_TOOL_DESCRIPTION.format(
            available_agents=subagent_description_str
        )
    elif "{available_agents}" in task_description:
        description = task_description.format(available_agents=subagent_description_str)
    else:
        description = task_description

    def _billable_call_update(
        subagent_type: str, runtime: ToolRuntime
    ) -> dict[str, Any]:
        """Build the per-call ``billable_calls`` delta plus an optional soft-cap warning.

        Always emits ``{subagent_type: 1}`` (a reducer accumulates it); when this
        call would cross the threshold, also adds a soft ``messages`` entry so the
        orchestrator self-limits on its next step.
        """
        delta: dict[str, Any] = {"billable_calls": {subagent_type: 1}}
        threshold = DEFAULT_SUBAGENT_BILLABLE_THRESHOLD
        if threshold <= 0:
            return delta
        prior = runtime.state.get("billable_calls") or {}
        # Count int values only so a malformed checkpoint can't crash us.
        prior_total = sum(v for v in prior.values() if isinstance(v, int))
        new_total = prior_total + 1
        if prior_total < threshold <= new_total:
            warn = (
                f"[budget warning] This turn has dispatched {new_total} "
                f"subagent calls (soft cap = {threshold}). Wrap up the "
                "user's request with what you have rather than launching "
                "more specialists; surface a partial answer if needed."
            )
            delta["_billable_warn_text"] = warn
        return delta

    def _attach_billable(
        cmd: Command, subagent_type: str, runtime: ToolRuntime
    ) -> Command:
        """Merge the per-call billable counter (and warning) into ``cmd``."""
        delta = _billable_call_update(subagent_type, runtime)
        warn_text = delta.pop("_billable_warn_text", None)
        # Copy so we don't mutate state shared with other tool returns.
        update = dict(getattr(cmd, "update", {}) or {})
        for key, value in delta.items():
            update[key] = value
        if warn_text:
            existing_msgs = list(update.get("messages") or [])
            existing_msgs.append(
                ToolMessage(content=warn_text, tool_call_id=runtime.tool_call_id)
            )
            update["messages"] = existing_msgs
        return Command(update=update)

    def _safe_message_text(msg: Any) -> str:
        """Pull text out of a BaseMessage without using the ``.text`` property.

        ``.text`` crashes when ``content`` is ``None`` (common for tool-call
        AIMessages), and ``getattr`` won't catch it, so read ``content`` directly.
        """
        try:
            content = getattr(msg, "content", None)
        except Exception:
            content = None
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for block in content:
                if isinstance(block, str):
                    parts.append(block)
                elif isinstance(block, dict):
                    block_text = block.get("text") or block.get("content")
                    if isinstance(block_text, str):
                        parts.append(block_text)
            return " ".join(parts)
        return str(content)

    def _build_tool_trace(messages: list[Any]) -> list[dict[str, Any]]:
        """Compress the subagent's messages into a compact tool trace.

        Entries (``{tool, status, preview}``) ride on the ToolMessage's
        ``additional_kwargs["surf_tool_trace"]`` for UI/observability; the LLM
        never sees them.
        """
        trace: list[dict[str, Any]] = []
        for msg in messages:
            tool_name = getattr(msg, "name", None)
            tool_call_id_attr = getattr(msg, "tool_call_id", None)
            if not tool_name and not tool_call_id_attr:
                # Only ToolMessages carry either field.
                continue
            status = getattr(msg, "status", None) or "ok"
            preview = _safe_message_text(msg).strip().replace("\n", " ")
            if len(preview) > 120:
                preview = preview[:117] + "..."
            trace.append(
                {
                    "tool": tool_name or "<unknown>",
                    "status": status,
                    "preview": preview,
                }
            )
        return trace

    def _return_command_with_state_update(result: dict, tool_call_id: str) -> Command:
        if "messages" not in result:
            msg = (
                "CompiledSubAgent must return a state containing a 'messages' key. "
                "Custom StateGraphs used with CompiledSubAgent should include 'messages' "
                "in their state schema to communicate results back to the main agent."
            )
            raise ValueError(msg)

        state_update = {k: v for k, v in result.items() if k not in EXCLUDED_STATE_KEYS}
        messages = result["messages"]
        if not messages:
            msg = (
                "CompiledSubAgent returned an empty 'messages' list. "
                "Subagents must produce at least one message so the parent has "
                "output to forward back to the user."
            )
            raise ValueError(msg)
        message_text = _safe_message_text(messages[-1]).rstrip()
        # Trace is observability-only; never let a bad frame kill the turn.
        try:
            tool_trace = _build_tool_trace(messages)
        except Exception:
            logger.exception(
                "Failed to build tool_trace for subagent return; "
                "continuing without trace."
            )
            tool_trace = []
        tool_msg = ToolMessage(message_text, tool_call_id=tool_call_id)
        if tool_trace:
            # surf_ prefix avoids collision with provider keys (e.g. cache_control).
            tool_msg.additional_kwargs["surf_tool_trace"] = tool_trace
        return Command(
            update={
                **state_update,
                "messages": [tool_msg],
            }
        )

    def _resolve_context_hint(
        subagent_type: str, description: str, runtime: ToolRuntime
    ) -> str | None:
        """Run the per-subagent hint provider; swallow & log any exception."""
        provider = subagent_hint_providers.get(subagent_type)
        if provider is None:
            return None
        try:
            hint = provider(runtime.state, description)
        except Exception:
            logger.exception(
                "Context-hint provider for subagent %r raised; skipping hint.",
                subagent_type,
            )
            return None
        if not hint or not isinstance(hint, str):
            return None
        cleaned = hint.strip()
        return cleaned or None

    def _forward_mention_pins(subagent_state: dict, runtime: ToolRuntime) -> None:
        """Carry the turn's ``@``-mention pins from main context into subagent state.

        Subagents are compiled without a ``context_schema`` and invoked without
        ``context=``, so ``runtime.context`` (which holds the ``@``-mentioned
        document/folder ids) does not reach them. The ``task`` tool runs in the
        main runtime, which *does* have the context, so we copy the pins into the
        forwarded state where ``search_knowledge_base`` reads them. Only set keys
        when present so we never clobber pins already on state (e.g. nested
        ``ask_knowledge_base`` re-entry).
        """
        ctx = getattr(runtime, "context", None)
        if ctx is None:
            return
        for state_key, ctx_attr in (
            ("mentioned_document_ids", "mentioned_document_ids"),
            ("mentioned_folder_ids", "mentioned_folder_ids"),
        ):
            value = getattr(ctx, ctx_attr, None)
            if value:
                subagent_state[state_key] = list(value)

    def _validate_and_prepare_state(
        subagent_type: str, description: str, runtime: ToolRuntime
    ) -> tuple[Runnable, dict]:
        subagent = resolve_subagent(subagent_type)
        subagent_state = {
            k: v for k, v in runtime.state.items() if k not in EXCLUDED_STATE_KEYS
        }
        _forward_mention_pins(subagent_state, runtime)
        hint = _resolve_context_hint(subagent_type, description, runtime)
        if hint:
            # Tagged block so the subagent prompt can pattern-match the section.
            payload = f"<context_hint>\n{hint}\n</context_hint>\n\n{description}"
        else:
            payload = description
        subagent_state["messages"] = [HumanMessage(content=payload)]
        return subagent, subagent_state

    def _merge_batch_results(
        results: list[tuple[int, str, dict | str, dict | None]],
        runtime: ToolRuntime,
    ) -> Command:
        """Combine per-child results into one Command with an aggregate ToolMessage.

        ``results`` tuples are ``(task_index, subagent_type, payload_or_error,
        child_state_update)``; output blocks are sorted by index so the LLM can
        map them back to dispatch order, and each child contributes a
        ``billable_calls`` increment to match single-mode accounting.
        """
        results.sort(key=lambda r: r[0])
        merged_state: dict[str, Any] = {}
        billable_delta: dict[str, int] = {}
        message_blocks: list[str] = []
        batch_trace: list[dict[str, Any]] = []
        for task_index, subagent_type, payload, state_update in results:
            billable_delta[subagent_type] = billable_delta.get(subagent_type, 0) + 1
            if isinstance(payload, str):
                # Pre-flight error or per-task exception text.
                message_blocks.append(f"[task {task_index}] {payload}")
                batch_trace.append(
                    {
                        "task_index": task_index,
                        "subagent_type": subagent_type,
                        "status": "error",
                        "tool_trace": [],
                    }
                )
                continue
            messages = payload.get("messages") or []
            last_text = _safe_message_text(messages[-1]).rstrip() if messages else ""
            message_blocks.append(f"[task {task_index}] {last_text or '<empty>'}")
            try:
                child_trace = _build_tool_trace(messages)
            except Exception:
                logger.exception(
                    "Failed to build tool_trace for batch task_index=%d; continuing.",
                    task_index,
                )
                child_trace = []
            batch_trace.append(
                {
                    "task_index": task_index,
                    "subagent_type": subagent_type,
                    "status": "ok",
                    "tool_trace": child_trace,
                }
            )
            if state_update:
                # Later tasks win on scalar collisions; reducer-backed fields
                # accumulate at apply time.
                merged_state.update(state_update)
        aggregate = "\n\n".join(message_blocks)
        aggregate_msg = ToolMessage(
            content=aggregate, tool_call_id=runtime.tool_call_id
        )
        if batch_trace:
            aggregate_msg.additional_kwargs["surf_tool_trace"] = batch_trace
        update: dict[str, Any] = {
            **merged_state,
            "billable_calls": billable_delta,
            "messages": [aggregate_msg],
        }
        # Soft-cap warning: check the cumulative count after attribution.
        threshold = DEFAULT_SUBAGENT_BILLABLE_THRESHOLD
        if threshold > 0:
            prior = runtime.state.get("billable_calls") or {}
            prior_total = sum(v for v in prior.values() if isinstance(v, int))
            new_total = prior_total + sum(billable_delta.values())
            if prior_total < threshold <= new_total:
                update["messages"].append(
                    ToolMessage(
                        content=(
                            f"[budget warning] This turn has dispatched "
                            f"{new_total} subagent calls (soft cap = "
                            f"{threshold}). Wrap up the user's request with "
                            "what you have rather than launching more "
                            "specialists; surface a partial answer if needed."
                        ),
                        tool_call_id=runtime.tool_call_id,
                    )
                )
        return Command(update=update)

    async def _ainvoke_one_batch_child(
        *,
        task_index: int,
        subagent_type: str,
        description: str,
        runtime: ToolRuntime,
        semaphore: asyncio.Semaphore,
    ) -> tuple[int, str, dict | str, dict | None]:
        """Run one child of a batched ``task`` call under the concurrency cap.

        Errors are returned as text (slot 2) so one child's failure doesn't abort
        the batch. A child's ``GraphInterrupt`` is a hard failure for that child:
        batched HITL is intentionally out of scope.
        """
        async with semaphore:
            if subagent_type not in subagent_names:
                allowed_types = ", ".join([f"`{k}`" for k in subagent_names])
                return (
                    task_index,
                    subagent_type,
                    (
                        f"Subagent {subagent_type!r} does not exist; "
                        f"allowed: {allowed_types}"
                    ),
                    None,
                )
            subagent, subagent_state = _validate_and_prepare_state(
                subagent_type, description, runtime
            )
            sub_config = subagent_invoke_config(runtime)
            started_at = time.perf_counter()
            try:
                result = await _ainvoke_with_timeout(
                    subagent.ainvoke(subagent_state, config=sub_config),
                    subagent_type=subagent_type,
                    started_at=started_at,
                )
            except SubagentInvokeTimeoutError as exc:
                logger.warning(
                    "Batch child %d (%s) timed out after %.1fs",
                    task_index,
                    subagent_type,
                    exc.elapsed_seconds,
                )
                return (task_index, subagent_type, str(exc), None)
            except GraphInterrupt:
                # Batched HITL unsupported; fail this child so the batch finishes.
                logger.warning(
                    "Batch child %d (%s) raised GraphInterrupt; batched HITL "
                    "is not supported. Re-dispatch this task as a single "
                    "(non-batched) `task(...)` call to get the HITL prompt.",
                    task_index,
                    subagent_type,
                )
                return (
                    task_index,
                    subagent_type,
                    (
                        f"Subagent {subagent_type!r} needs human approval. "
                        "Re-dispatch this task as a single (non-batched) "
                        "`task(...)` call so the approval card can be shown."
                    ),
                    None,
                )
            except Exception as exc:
                logger.exception(
                    "Batch child %d (%s) raised: %s",
                    task_index,
                    subagent_type,
                    exc,
                )
                return (
                    task_index,
                    subagent_type,
                    f"Subagent {subagent_type!r} error: {exc}",
                    None,
                )
            child_state_update = {
                k: v for k, v in result.items() if k not in EXCLUDED_STATE_KEYS
            }
            return (task_index, subagent_type, result, child_state_update)

    def _coerce_batch_arg(tasks: Any) -> list[dict] | str:
        """Rescue common LLM malformations of the ``tasks`` argument.

        Recovers a JSON-encoded array string and a single dict (instead of a
        1-element array), logging a WARN. Unrecoverable shapes return a string
        the caller surfaces as the tool error.
        """
        if isinstance(tasks, list):
            return tasks
        if isinstance(tasks, dict):
            logger.warning(
                "task: `tasks` was a single dict; coercing to a 1-element list. "
                "Orchestrators should send `tasks=[{...}]` directly."
            )
            return [tasks]
        if isinstance(tasks, str):
            stripped = tasks.strip()
            if not stripped:
                return "tasks: argument is empty."
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError as exc:
                return (
                    f"tasks: argument is a string but not valid JSON ({exc.msg}). "
                    "Send a JSON array of `{description, subagent_type}` objects."
                )
            logger.warning(
                "task: `tasks` was a JSON-encoded string; parsed to %s. "
                "Orchestrators should send a JSON array directly.",
                type(parsed).__name__,
            )
            return _coerce_batch_arg(parsed)
        return (
            f"tasks: unsupported type {type(tasks).__name__}; expected an array "
            "of `{description, subagent_type}` objects."
        )

    async def _adispatch_batch(
        tasks: list[dict], runtime: ToolRuntime
    ) -> Command | str:
        """Fan out the ``tasks`` array (size- and concurrency-capped).

        Returns one Command; the LLM sees one ``[task <index>]``-prefixed block
        per child, in input order.
        """
        if not tasks:
            return "tasks: array is empty; nothing to dispatch."
        if len(tasks) > MAX_SUBAGENT_BATCH_SIZE:
            return (
                f"tasks: too many children ({len(tasks)}); "
                f"max is {MAX_SUBAGENT_BATCH_SIZE}. Split the batch."
            )
        normalized: list[tuple[int, str, str]] = []
        for idx, item in enumerate(tasks):
            if not isinstance(item, dict):
                return (
                    f"tasks[{idx}]: must be an object with description+subagent_type."
                )
            description = item.get("description")
            subagent_type = item.get("subagent_type")
            if not isinstance(description, str) or not description.strip():
                return f"tasks[{idx}]: missing or empty 'description'."
            if not isinstance(subagent_type, str) or not subagent_type.strip():
                return f"tasks[{idx}]: missing or empty 'subagent_type'."
            normalized.append((idx, subagent_type.strip(), description))
        semaphore = asyncio.Semaphore(DEFAULT_SUBAGENT_BATCH_CONCURRENCY)
        coros = [
            _ainvoke_one_batch_child(
                task_index=idx,
                subagent_type=subagent_type,
                description=description,
                runtime=runtime,
                semaphore=semaphore,
            )
            for idx, subagent_type, description in normalized
        ]
        results = await asyncio.gather(*coros)
        return _merge_batch_results(list(results), runtime)

    def task(
        description: Annotated[
            str | None,
            "Single-mode: a detailed task description for the subagent. Required unless `tasks` is provided.",
        ] = None,
        subagent_type: Annotated[
            str | None,
            "Single-mode: the type of subagent to use. Required unless `tasks` is provided.",
        ] = None,
        runtime: ToolRuntime = None,  # type: ignore[assignment]
        tasks: Annotated[
            list[dict] | None,
            (
                "Batch-mode: array of `{description, subagent_type}` objects. "
                "Synchronous path does not support batch mode; orchestrators "
                "must use the async event loop to fan out."
            ),
        ] = None,
    ) -> str | Command:
        if tasks is not None:
            return (
                "task: batch mode (`tasks=[...]`) is only supported on the async "
                "path. SurfSense orchestrators always run in an event loop, so "
                "this should never fire — file a bug if you see it."
            )
        if not description or not subagent_type:
            return (
                "task: must provide either single-mode (`description`+`subagent_type`) "
                "or batch-mode (`tasks`)."
            )
        if subagent_type not in subagent_names:
            allowed_types = ", ".join([f"`{k}`" for k in subagent_names])
            return (
                f"We cannot invoke subagent {subagent_type} because it does not exist, "
                f"the only allowed types are {allowed_types}"
            )
        if not runtime.tool_call_id:
            raise ValueError("Tool call ID is required for subagent invocation")
        subagent, subagent_state = _validate_and_prepare_state(
            subagent_type, description, runtime
        )
        sub_config = subagent_invoke_config(runtime)

        # Resume bridge: forward the parent's stashed decision into the
        # subagent's pending ``interrupt()``, targeted by id.
        pending_id: str | None = None
        pending_value: Any = None
        get_state = getattr(subagent, "get_state", None)
        if callable(get_state):
            try:
                snapshot = get_state(sub_config)
                pending_id, pending_value = get_first_pending_subagent_interrupt(
                    snapshot
                )
            except Exception:
                # Fail loud if a resume is queued: silent fallback would
                # replay the original interrupt to the user.
                if has_surfsense_resume(runtime):
                    logger.exception(
                        "Subagent %r get_state raised with resume queued; re-raising.",
                        subagent_type,
                    )
                    raise
                logger.debug(
                    "Subagent get_state failed; falling back to fresh invoke",
                    exc_info=True,
                )

        invoke_path = "resume" if pending_value is not None else "fresh"
        invoke_start = time.perf_counter()
        invoke_outcome = "ok"
        if pending_value is not None:
            resume_value = consume_surfsense_resume(runtime)
            if resume_value is None:
                # A pending interrupt must have a queued resume; otherwise replay
                # would silently re-prompt the user. Raise instead.
                raise RuntimeError(
                    f"Subagent {subagent_type!r} has a pending interrupt but no "
                    "surfsense_resume_value on config; resume bridge is broken."
                )
            expected = hitlrequest_action_count(pending_value)
            resume_value = fan_out_decisions_to_match(resume_value, expected)
            # Stop the parent's resume leaking into subagent interrupts via
            # langgraph's parent_scratchpad fallback.
            drain_parent_null_resume(runtime)
            with ot.subagent_invoke_span(
                subagent_type=subagent_type, path=invoke_path
            ) as sp:
                try:
                    result = subagent.invoke(
                        build_resume_command(resume_value, pending_id),
                        config=sub_config,
                    )
                    sp.set_attribute("subagent.outcome", invoke_outcome)
                except GraphInterrupt as gi:
                    invoke_outcome = "interrupted"
                    sp.set_attribute("subagent.outcome", invoke_outcome)
                    ot_metrics.record_subagent_invoke_duration(
                        (time.perf_counter() - invoke_start) * 1000,
                        subagent_type=subagent_type,
                        path=invoke_path,
                        outcome=invoke_outcome,
                    )
                    ot_metrics.record_subagent_invoke_outcome(
                        subagent_type=subagent_type,
                        path=invoke_path,
                        outcome=invoke_outcome,
                    )
                    _reraise_stamped_subagent_interrupt(gi, runtime.tool_call_id)
                except Exception:
                    invoke_outcome = "error"
                    sp.set_attribute("subagent.outcome", invoke_outcome)
                    ot_metrics.record_subagent_invoke_duration(
                        (time.perf_counter() - invoke_start) * 1000,
                        subagent_type=subagent_type,
                        path=invoke_path,
                        outcome=invoke_outcome,
                    )
                    ot_metrics.record_subagent_invoke_outcome(
                        subagent_type=subagent_type,
                        path=invoke_path,
                        outcome=invoke_outcome,
                    )
                    raise
        else:
            with ot.subagent_invoke_span(
                subagent_type=subagent_type, path=invoke_path
            ) as sp:
                try:
                    result = subagent.invoke(subagent_state, config=sub_config)
                    sp.set_attribute("subagent.outcome", invoke_outcome)
                except GraphInterrupt as gi:
                    invoke_outcome = "interrupted"
                    sp.set_attribute("subagent.outcome", invoke_outcome)
                    ot_metrics.record_subagent_invoke_duration(
                        (time.perf_counter() - invoke_start) * 1000,
                        subagent_type=subagent_type,
                        path=invoke_path,
                        outcome=invoke_outcome,
                    )
                    ot_metrics.record_subagent_invoke_outcome(
                        subagent_type=subagent_type,
                        path=invoke_path,
                        outcome=invoke_outcome,
                    )
                    _reraise_stamped_subagent_interrupt(gi, runtime.tool_call_id)
                except Exception:
                    invoke_outcome = "error"
                    sp.set_attribute("subagent.outcome", invoke_outcome)
                    ot_metrics.record_subagent_invoke_duration(
                        (time.perf_counter() - invoke_start) * 1000,
                        subagent_type=subagent_type,
                        path=invoke_path,
                        outcome=invoke_outcome,
                    )
                    ot_metrics.record_subagent_invoke_outcome(
                        subagent_type=subagent_type,
                        path=invoke_path,
                        outcome=invoke_outcome,
                    )
                    raise
        invoke_elapsed_ms = (time.perf_counter() - invoke_start) * 1000
        ot_metrics.record_subagent_invoke_duration(
            invoke_elapsed_ms,
            subagent_type=subagent_type,
            path=invoke_path,
            outcome=invoke_outcome,
        )
        ot_metrics.record_subagent_invoke_outcome(
            subagent_type=subagent_type,
            path=invoke_path,
            outcome=invoke_outcome,
        )
        return _return_command_with_state_update(result, runtime.tool_call_id)

    async def atask(
        description: Annotated[
            str | None,
            "Single-mode: a detailed task description for the subagent. Required unless `tasks` is provided.",
        ] = None,
        subagent_type: Annotated[
            str | None,
            "Single-mode: the type of subagent to use. Required unless `tasks` is provided.",
        ] = None,
        runtime: ToolRuntime = None,  # type: ignore[assignment]
        tasks: Annotated[
            list[dict] | None,
            (
                "Batch-mode: array of `{description, subagent_type}` objects "
                "to fan out concurrently (max "
                f"{MAX_SUBAGENT_BATCH_SIZE}, concurrency "
                f"{DEFAULT_SUBAGENT_BATCH_CONCURRENCY}). Mutually exclusive "
                "with single-mode args. Batched children do not support "
                "human-in-the-loop interrupts; re-dispatch as single mode "
                "if a child needs approval."
            ),
        ] = None,
    ) -> str | Command:
        atask_start = time.perf_counter()
        # Ops kill switch: short-circuit every task() call for this workspace
        # so the orchestrator stops hammering downstream APIs.
        if await is_spawn_paused(search_space_id):
            logger.warning(
                "[hitl_route] atask SPAWN_PAUSED: search_space_id=%s tool_call_id=%s",
                search_space_id,
                runtime.tool_call_id,
            )
            return (
                "task: subagent dispatch is currently paused for this workspace. "
                "Acknowledge to the user that delegation is temporarily disabled "
                "(ops kill switch); do not retry until the pause is lifted."
            )
        if tasks is not None:
            if description or subagent_type:
                return (
                    "task: cannot combine `tasks` with `description`/`subagent_type`. "
                    "Use either single-mode (description+subagent_type) or batch-mode (tasks)."
                )
            if not runtime.tool_call_id:
                raise ValueError("Tool call ID is required for subagent invocation")
            coerced = _coerce_batch_arg(tasks)
            if isinstance(coerced, str):
                return coerced
            logger.info(
                "[hitl_route] atask BATCH ENTRY: size=%d tool_call_id=%s",
                len(coerced),
                runtime.tool_call_id,
            )
            return await _adispatch_batch(coerced, runtime)
        if not description or not subagent_type:
            return (
                "task: must provide either single-mode (`description`+`subagent_type`) "
                "or batch-mode (`tasks`)."
            )
        logger.info(
            "[hitl_route] atask ENTRY: subagent_type=%r tool_call_id=%s",
            subagent_type,
            runtime.tool_call_id,
        )
        if subagent_type not in subagent_names:
            allowed_types = ", ".join([f"`{k}`" for k in subagent_names])
            return (
                f"We cannot invoke subagent {subagent_type} because it does not exist, "
                f"the only allowed types are {allowed_types}"
            )
        if not runtime.tool_call_id:
            raise ValueError("Tool call ID is required for subagent invocation")
        subagent, subagent_state = _validate_and_prepare_state(
            subagent_type, description, runtime
        )
        sub_config = subagent_invoke_config(runtime)

        # Resume bridge — see ``task`` above.
        pending_id: str | None = None
        pending_value: Any = None
        aget_state_elapsed = 0.0
        aget_state = getattr(subagent, "aget_state", None)
        if callable(aget_state):
            aget_state_start = time.perf_counter()
            try:
                snapshot = await aget_state(sub_config)
                pending_id, pending_value = get_first_pending_subagent_interrupt(
                    snapshot
                )
            except Exception:
                if has_surfsense_resume(runtime):
                    logger.exception(
                        "Subagent %r aget_state raised with resume queued; re-raising.",
                        subagent_type,
                    )
                    raise
                logger.debug(
                    "Subagent aget_state failed; falling back to fresh ainvoke",
                    exc_info=True,
                )
            finally:
                aget_state_elapsed = time.perf_counter() - aget_state_start

        invoke_path = "resume" if pending_value is not None else "fresh"
        ainvoke_start = time.perf_counter()
        ainvoke_outcome = "ok"
        try:
            if pending_value is not None:
                resume_value = consume_surfsense_resume(runtime)
                if resume_value is None:
                    raise RuntimeError(
                        f"Subagent {subagent_type!r} has a pending interrupt but no "
                        "surfsense_resume_value on config; resume bridge is broken."
                    )
                expected = hitlrequest_action_count(pending_value)
                resume_value = fan_out_decisions_to_match(resume_value, expected)
                # Stop the parent's resume leaking into subagent interrupts via
                # langgraph's parent_scratchpad fallback.
                drain_parent_null_resume(runtime)
                with ot.subagent_invoke_span(
                    subagent_type=subagent_type, path=invoke_path
                ) as sp:
                    try:
                        result = await _ainvoke_with_timeout(
                            subagent.ainvoke(
                                build_resume_command(resume_value, pending_id),
                                config=sub_config,
                            ),
                            subagent_type=subagent_type,
                            started_at=ainvoke_start,
                        )
                        sp.set_attribute("subagent.outcome", ainvoke_outcome)
                    except SubagentInvokeTimeoutError as exc:
                        ainvoke_outcome = "timeout"
                        sp.set_attribute("subagent.outcome", ainvoke_outcome)
                        ot_metrics.record_subagent_invoke_duration(
                            (time.perf_counter() - ainvoke_start) * 1000,
                            subagent_type=subagent_type,
                            path=invoke_path,
                            outcome=ainvoke_outcome,
                        )
                        ot_metrics.record_subagent_invoke_outcome(
                            subagent_type=subagent_type,
                            path=invoke_path,
                            outcome=ainvoke_outcome,
                        )
                        logger.warning(
                            "Subagent %r ainvoke (resume) timed out after %.1fs",
                            subagent_type,
                            exc.elapsed_seconds,
                        )
                        return _synthesize_timeout_command(
                            exc, tool_call_id=runtime.tool_call_id
                        )
                    except GraphInterrupt as gi:
                        ainvoke_outcome = "interrupted"
                        sp.set_attribute("subagent.outcome", ainvoke_outcome)
                        ot_metrics.record_subagent_invoke_duration(
                            (time.perf_counter() - ainvoke_start) * 1000,
                            subagent_type=subagent_type,
                            path=invoke_path,
                            outcome=ainvoke_outcome,
                        )
                        ot_metrics.record_subagent_invoke_outcome(
                            subagent_type=subagent_type,
                            path=invoke_path,
                            outcome=ainvoke_outcome,
                        )
                        _perf_log.info(
                            "[hitl_route] atask EXIT subagent_type=%r path=%s outcome=%s "
                            "aget_state=%.3fs ainvoke=%.3fs total=%.3fs",
                            subagent_type,
                            invoke_path,
                            ainvoke_outcome,
                            aget_state_elapsed,
                            time.perf_counter() - ainvoke_start,
                            time.perf_counter() - atask_start,
                        )
                        _reraise_stamped_subagent_interrupt(gi, runtime.tool_call_id)
                    except Exception:
                        ainvoke_outcome = "error"
                        sp.set_attribute("subagent.outcome", ainvoke_outcome)
                        ot_metrics.record_subagent_invoke_duration(
                            (time.perf_counter() - ainvoke_start) * 1000,
                            subagent_type=subagent_type,
                            path=invoke_path,
                            outcome=ainvoke_outcome,
                        )
                        ot_metrics.record_subagent_invoke_outcome(
                            subagent_type=subagent_type,
                            path=invoke_path,
                            outcome=ainvoke_outcome,
                        )
                        raise
            else:
                with ot.subagent_invoke_span(
                    subagent_type=subagent_type, path=invoke_path
                ) as sp:
                    try:
                        result = await _ainvoke_with_timeout(
                            subagent.ainvoke(subagent_state, config=sub_config),
                            subagent_type=subagent_type,
                            started_at=ainvoke_start,
                        )
                        sp.set_attribute("subagent.outcome", ainvoke_outcome)
                    except SubagentInvokeTimeoutError as exc:
                        ainvoke_outcome = "timeout"
                        sp.set_attribute("subagent.outcome", ainvoke_outcome)
                        ot_metrics.record_subagent_invoke_duration(
                            (time.perf_counter() - ainvoke_start) * 1000,
                            subagent_type=subagent_type,
                            path=invoke_path,
                            outcome=ainvoke_outcome,
                        )
                        ot_metrics.record_subagent_invoke_outcome(
                            subagent_type=subagent_type,
                            path=invoke_path,
                            outcome=ainvoke_outcome,
                        )
                        logger.warning(
                            "Subagent %r ainvoke (fresh) timed out after %.1fs",
                            subagent_type,
                            exc.elapsed_seconds,
                        )
                        return _synthesize_timeout_command(
                            exc, tool_call_id=runtime.tool_call_id
                        )
                    except GraphInterrupt as gi:
                        ainvoke_outcome = "interrupted"
                        sp.set_attribute("subagent.outcome", ainvoke_outcome)
                        ot_metrics.record_subagent_invoke_duration(
                            (time.perf_counter() - ainvoke_start) * 1000,
                            subagent_type=subagent_type,
                            path=invoke_path,
                            outcome=ainvoke_outcome,
                        )
                        ot_metrics.record_subagent_invoke_outcome(
                            subagent_type=subagent_type,
                            path=invoke_path,
                            outcome=ainvoke_outcome,
                        )
                        _perf_log.info(
                            "[hitl_route] atask EXIT subagent_type=%r path=%s outcome=%s "
                            "aget_state=%.3fs ainvoke=%.3fs total=%.3fs",
                            subagent_type,
                            invoke_path,
                            ainvoke_outcome,
                            aget_state_elapsed,
                            time.perf_counter() - ainvoke_start,
                            time.perf_counter() - atask_start,
                        )
                        _reraise_stamped_subagent_interrupt(gi, runtime.tool_call_id)
                    except Exception:
                        ainvoke_outcome = "error"
                        sp.set_attribute("subagent.outcome", ainvoke_outcome)
                        ot_metrics.record_subagent_invoke_duration(
                            (time.perf_counter() - ainvoke_start) * 1000,
                            subagent_type=subagent_type,
                            path=invoke_path,
                            outcome=ainvoke_outcome,
                        )
                        ot_metrics.record_subagent_invoke_outcome(
                            subagent_type=subagent_type,
                            path=invoke_path,
                            outcome=ainvoke_outcome,
                        )
                        raise
            ainvoke_elapsed = time.perf_counter() - ainvoke_start
        except GraphInterrupt:
            raise

        merge_start = time.perf_counter()
        cmd = _return_command_with_state_update(result, runtime.tool_call_id)
        merge_elapsed = time.perf_counter() - merge_start
        _perf_log.info(
            "[hitl_route] atask EXIT subagent_type=%r path=%s outcome=%s "
            "aget_state=%.3fs ainvoke=%.3fs merge=%.3fs total=%.3fs",
            subagent_type,
            invoke_path,
            ainvoke_outcome,
            aget_state_elapsed,
            ainvoke_elapsed,
            merge_elapsed,
            time.perf_counter() - atask_start,
        )
        ot_metrics.record_subagent_invoke_duration(
            ainvoke_elapsed * 1000,
            subagent_type=subagent_type,
            path=invoke_path,
            outcome=ainvoke_outcome,
        )
        ot_metrics.record_subagent_invoke_outcome(
            subagent_type=subagent_type,
            path=invoke_path,
            outcome=ainvoke_outcome,
        )
        return _attach_billable(cmd, subagent_type, runtime)

    return StructuredTool.from_function(
        name="task",
        func=task,
        coroutine=atask,
        description=description,
    )
