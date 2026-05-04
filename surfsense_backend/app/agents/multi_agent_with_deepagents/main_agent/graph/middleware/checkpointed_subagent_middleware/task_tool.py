"""Build the ``task`` tool that invokes subagents with HITL bridging.

The tool's body is the only place where the parent and the subagent meet at
runtime: it reads the parent's stashed resume value, decides whether to send
fresh state or a targeted ``Command(resume=...)`` to the subagent, then
re-raises any new pending interrupt back to the parent.
"""

from __future__ import annotations

import logging
from typing import Annotated, Any

from deepagents.middleware.subagents import TASK_TOOL_DESCRIPTION
from langchain.tools import BaseTool, ToolRuntime
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.runnables import Runnable
from langchain_core.tools import StructuredTool
from langgraph.types import Command

from .config import extract_surfsense_resume, subagent_invoke_config
from .constants import EXCLUDED_STATE_KEYS
from .propagation import (
    amaybe_propagate_subagent_interrupt,
    maybe_propagate_subagent_interrupt,
)
from .resume import (
    build_resume_command,
    fan_out_decisions_to_match,
    hitlrequest_action_count,
    get_first_pending_subagent_interrupt,
)

logger = logging.getLogger(__name__)


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
        description = TASK_TOOL_DESCRIPTION.format(available_agents=subagent_description_str)
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
        message_text = (
            result["messages"][-1].text.rstrip() if result["messages"][-1].text else ""
        )
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
            "A detailed description of the task for the subagent to perform autonomously. Include all necessary context and specify the expected output format.",  # noqa: E501
        ],
        subagent_type: Annotated[
            str,
            "The type of subagent to use. Must be one of the available agent types listed in the tool description.",  # noqa: E501
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
                pending_id, pending_value = get_first_pending_subagent_interrupt(snapshot)
            except Exception:  # pragma: no cover - defensive
                logger.debug(
                    "Subagent get_state failed; falling back to fresh invoke",
                    exc_info=True,
                )

        if pending_value is not None:
            resume_value = extract_surfsense_resume(runtime)
            if resume_value is not None:
                expected = hitlrequest_action_count(pending_value)
                resume_value = fan_out_decisions_to_match(resume_value, expected)
                logger.info(
                    "Forwarding surfsense_resume_value into subagent %r "
                    "(action_requests=%d, targeted_id=%s)",
                    subagent_type,
                    expected,
                    pending_id is not None,
                )
                result = subagent.invoke(
                    build_resume_command(resume_value, pending_id),
                    config=sub_config,
                )
            else:
                logger.warning(
                    "Subagent %r has pending interrupt but no surfsense_resume_value "
                    "on config — replaying with fresh state (interrupt will re-fire).",
                    subagent_type,
                )
                result = subagent.invoke(subagent_state, config=sub_config)
        else:
            result = subagent.invoke(subagent_state, config=sub_config)
        maybe_propagate_subagent_interrupt(subagent, sub_config, subagent_type)
        return _return_command_with_state_update(result, runtime.tool_call_id)

    async def atask(
        description: Annotated[
            str,
            "A detailed description of the task for the subagent to perform autonomously. Include all necessary context and specify the expected output format.",  # noqa: E501
        ],
        subagent_type: Annotated[
            str,
            "The type of subagent to use. Must be one of the available agent types listed in the tool description.",  # noqa: E501
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

        # Resume bridge — see ``task`` above.
        pending_id: str | None = None
        pending_value: Any = None
        aget_state = getattr(subagent, "aget_state", None)
        if callable(aget_state):
            try:
                snapshot = await aget_state(sub_config)
                pending_id, pending_value = get_first_pending_subagent_interrupt(snapshot)
            except Exception:  # pragma: no cover - defensive
                logger.debug(
                    "Subagent aget_state failed; falling back to fresh ainvoke",
                    exc_info=True,
                )

        if pending_value is not None:
            resume_value = extract_surfsense_resume(runtime)
            if resume_value is not None:
                expected = hitlrequest_action_count(pending_value)
                resume_value = fan_out_decisions_to_match(resume_value, expected)
                logger.info(
                    "Forwarding surfsense_resume_value into subagent %r "
                    "(action_requests=%d, targeted_id=%s)",
                    subagent_type,
                    expected,
                    pending_id is not None,
                )
                result = await subagent.ainvoke(
                    build_resume_command(resume_value, pending_id),
                    config=sub_config,
                )
            else:
                logger.warning(
                    "Subagent %r has pending interrupt but no surfsense_resume_value "
                    "on config — replaying with fresh state (interrupt will re-fire).",
                    subagent_type,
                )
                result = await subagent.ainvoke(subagent_state, config=sub_config)
        else:
            result = await subagent.ainvoke(subagent_state, config=sub_config)
        await amaybe_propagate_subagent_interrupt(subagent, sub_config, subagent_type)
        return _return_command_with_state_update(result, runtime.tool_call_id)

    return StructuredTool.from_function(
        name="task",
        func=task,
        coroutine=atask,
        description=description,
    )
