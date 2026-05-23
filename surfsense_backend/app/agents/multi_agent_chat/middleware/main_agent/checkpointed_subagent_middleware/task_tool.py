"""Build the ``task`` tool that invokes subagents with HITL bridging.

The tool's body is the only place where the parent and the subagent meet at
runtime: it reads the parent's stashed resume value, decides whether to send
fresh state or a targeted ``Command(resume=...)`` to the subagent, then
re-raises any new pending interrupt back to the parent.
"""

from __future__ import annotations

import logging
import time
from typing import Annotated, Any, NoReturn

from deepagents.middleware.subagents import TASK_TOOL_DESCRIPTION
from langchain.tools import BaseTool, ToolRuntime
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.runnables import Runnable
from langchain_core.tools import StructuredTool
from langgraph.errors import GraphInterrupt
from langgraph.types import Command, Interrupt

from app.observability import metrics as ot_metrics, otel as ot
from app.utils.perf import get_perf_logger

from .config import (
    consume_surfsense_resume,
    drain_parent_null_resume,
    has_surfsense_resume,
    subagent_invoke_config,
)
from .constants import EXCLUDED_STATE_KEYS
from .propagation import wrap_with_tool_call_id
from .resume import (
    build_resume_command,
    fan_out_decisions_to_match,
    get_first_pending_subagent_interrupt,
    hitlrequest_action_count,
)

logger = logging.getLogger(__name__)
_perf_log = get_perf_logger()


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
) -> BaseTool:
    """Upstream ``_build_task_tool`` + parent ``runtime.config`` propagation + resume bridging."""
    subagent_graphs: dict[str, Runnable] = {
        spec["name"]: spec["runnable"] for spec in subagents
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
        last_text = getattr(messages[-1], "text", None) or ""
        message_text = last_text.rstrip()
        return Command(
            update={
                **state_update,
                "messages": [ToolMessage(message_text, tool_call_id=tool_call_id)],
            }
        )

    def _validate_and_prepare_state(
        subagent_type: str, description: str, runtime: ToolRuntime
    ) -> tuple[Runnable, dict]:
        subagent = subagent_graphs[subagent_type]
        subagent_state = {
            k: v for k, v in runtime.state.items() if k not in EXCLUDED_STATE_KEYS
        }
        subagent_state["messages"] = [HumanMessage(content=description)]
        return subagent, subagent_state

    def task(
        description: Annotated[
            str,
            "A detailed description of the task for the subagent to perform autonomously. Include all necessary context and specify the expected output format.",
        ],
        subagent_type: Annotated[
            str,
            "The type of subagent to use. Must be one of the available agent types listed in the tool description.",
        ],
        runtime: ToolRuntime,
    ) -> str | Command:
        if subagent_type not in subagent_graphs:
            allowed_types = ", ".join([f"`{k}`" for k in subagent_graphs])
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
                # Bridge invariant: a queued resume must accompany any pending
                # subagent interrupt. Fall-through replay would silently re-prompt
                # the user; raise so the streaming layer surfaces a clear error.
                raise RuntimeError(
                    f"Subagent {subagent_type!r} has a pending interrupt but no "
                    "surfsense_resume_value on config; resume bridge is broken."
                )
            expected = hitlrequest_action_count(pending_value)
            resume_value = fan_out_decisions_to_match(resume_value, expected)
            # Prevent the parent's resume payload from leaking into subagent
            # interrupts via langgraph's parent_scratchpad fallback.
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
            str,
            "A detailed description of the task for the subagent to perform autonomously. Include all necessary context and specify the expected output format.",
        ],
        subagent_type: Annotated[
            str,
            "The type of subagent to use. Must be one of the available agent types listed in the tool description.",
        ],
        runtime: ToolRuntime,
    ) -> str | Command:
        atask_start = time.perf_counter()
        logger.info(
            "[hitl_route] atask ENTRY: subagent_type=%r tool_call_id=%s",
            subagent_type,
            runtime.tool_call_id,
        )
        if subagent_type not in subagent_graphs:
            allowed_types = ", ".join([f"`{k}`" for k in subagent_graphs])
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
                # Prevent the parent's resume payload from leaking into subagent
                # interrupts via langgraph's parent_scratchpad fallback.
                drain_parent_null_resume(runtime)
                with ot.subagent_invoke_span(
                    subagent_type=subagent_type, path=invoke_path
                ) as sp:
                    try:
                        result = await subagent.ainvoke(
                            build_resume_command(resume_value, pending_id),
                            config=sub_config,
                        )
                        sp.set_attribute("subagent.outcome", ainvoke_outcome)
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
                        result = await subagent.ainvoke(
                            subagent_state, config=sub_config
                        )
                        sp.set_attribute("subagent.outcome", ainvoke_outcome)
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
        return cmd

    return StructuredTool.from_function(
        name="task",
        func=task,
        coroutine=atask,
        description=description,
    )
