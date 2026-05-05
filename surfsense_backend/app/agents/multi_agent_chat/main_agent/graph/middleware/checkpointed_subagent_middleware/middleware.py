"""SubAgent middleware that compiles each subagent against the parent checkpointer."""

from __future__ import annotations

from typing import Any, cast

from deepagents.backends.protocol import BackendFactory, BackendProtocol
from deepagents.middleware.subagents import (
    TASK_SYSTEM_PROMPT,
    CompiledSubAgent,
    SubAgent,
    SubAgentMiddleware,
)
from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain.chat_models import init_chat_model
from langgraph.types import Checkpointer

from .task_tool import build_task_tool_with_parent_config


class SurfSenseCheckpointedSubAgentMiddleware(SubAgentMiddleware):
    """``SubAgentMiddleware`` variant that compiles each subagent against the parent checkpointer."""

    def __init__(
        self,
        *,
        checkpointer: Checkpointer,
        backend: BackendProtocol | BackendFactory,
        subagents: list[SubAgent | CompiledSubAgent],
        system_prompt: str | None = TASK_SYSTEM_PROMPT,
        task_description: str | None = None,
    ) -> None:
        self._surf_checkpointer = checkpointer
        super(SubAgentMiddleware, self).__init__()
        if not subagents:
            raise ValueError(
                "At least one subagent must be specified when using the new API"
            )
        self._backend = backend
        self._subagents = subagents
        subagent_specs = self._surf_compile_subagent_graphs()
        task_tool = build_task_tool_with_parent_config(subagent_specs, task_description)
        if system_prompt and subagent_specs:
            agents_desc = "\n".join(
                f"- {s['name']}: {s['description']}" for s in subagent_specs
            )
            self.system_prompt = (
                system_prompt + "\n\nAvailable subagent types:\n" + agents_desc
            )
        else:
            self.system_prompt = system_prompt
        self.tools = [task_tool]

    def _surf_compile_subagent_graphs(self) -> list[dict[str, Any]]:
        """Mirror of ``SubAgentMiddleware._get_subagents`` that threads the parent checkpointer."""
        specs: list[dict[str, Any]] = []

        for spec in self._subagents:
            if "runnable" in spec:
                compiled = cast(CompiledSubAgent, spec)
                specs.append(
                    {
                        "name": compiled["name"],
                        "description": compiled["description"],
                        "runnable": compiled["runnable"],
                    }
                )
                continue

            if "model" not in spec:
                msg = f"SubAgent '{spec['name']}' must specify 'model'"
                raise ValueError(msg)
            if "tools" not in spec:
                msg = f"SubAgent '{spec['name']}' must specify 'tools'"
                raise ValueError(msg)

            model = spec["model"]
            if isinstance(model, str):
                model = init_chat_model(model)

            middleware: list[Any] = list(spec.get("middleware", []))

            interrupt_on = spec.get("interrupt_on")
            if interrupt_on:
                middleware.append(HumanInTheLoopMiddleware(interrupt_on=interrupt_on))

            specs.append(
                {
                    "name": spec["name"],
                    "description": spec["description"],
                    "runnable": create_agent(
                        model,
                        system_prompt=spec["system_prompt"],
                        tools=spec["tools"],
                        middleware=middleware,
                        name=spec["name"],
                        checkpointer=self._surf_checkpointer,
                    ),
                }
            )

        return specs
