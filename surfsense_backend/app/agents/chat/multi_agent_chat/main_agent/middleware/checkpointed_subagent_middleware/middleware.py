"""SubAgent middleware that compiles each subagent against the parent checkpointer."""

from __future__ import annotations

import time
from typing import Any, cast

from deepagents.backends.protocol import BackendFactory, BackendProtocol
from deepagents.middleware.subagents import (
    TASK_SYSTEM_PROMPT,
    CompiledSubAgent,
    SubAgent,
    SubAgentMiddleware,
)
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langgraph.types import Checkpointer

from app.agents.chat.multi_agent_chat.subagents.shared.spec import (
    SURF_CONTEXT_HINT_PROVIDER_KEY,
)
from app.utils.perf import get_perf_logger

from .task_tool import build_task_tool_with_parent_config

_perf_log = get_perf_logger()


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
        search_space_id: int | None = None,
    ) -> None:
        self._surf_checkpointer = checkpointer
        super(SubAgentMiddleware, self).__init__()
        if not subagents:
            raise ValueError(
                "At least one subagent must be specified when using the new API"
            )
        self._backend = backend
        self._subagents = subagents
        # Search-space id is captured at build time (the orchestrator runs in
        # exactly one search space for its lifetime). The spawn-paused kill
        # switch keys on it so an operator can quarantine one workspace
        # without affecting the rest of the deployment.
        self._search_space_id = search_space_id
        subagent_specs = self._surf_compile_subagent_graphs()
        task_tool = build_task_tool_with_parent_config(
            subagent_specs,
            task_description,
            search_space_id=search_space_id,
        )
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
        loop_start = time.perf_counter()
        timings: list[tuple[str, float, str]] = []  # (name, elapsed, source)

        for spec in self._subagents:
            spec_start = time.perf_counter()
            # Provider may be ``None`` (no hint), in which case task_tool
            # skips the prepend step. We forward the key unconditionally so
            # the registry shape is uniform.
            hint_provider = cast(dict, spec).get(SURF_CONTEXT_HINT_PROVIDER_KEY)
            if "runnable" in spec:
                compiled = cast(CompiledSubAgent, spec)
                specs.append(
                    {
                        "name": compiled["name"],
                        "description": compiled["description"],
                        "runnable": compiled["runnable"],
                        SURF_CONTEXT_HINT_PROVIDER_KEY: hint_provider,
                    }
                )
                timings.append(
                    (compiled["name"], time.perf_counter() - spec_start, "precompiled")
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
            tools_count = len(spec.get("tools") or [])
            mw_count = len(middleware)

            compile_start = time.perf_counter()
            runnable = create_agent(
                model,
                system_prompt=spec["system_prompt"],
                tools=spec["tools"],
                middleware=middleware,
                name=spec["name"],
                checkpointer=self._surf_checkpointer,
            )
            compile_elapsed = time.perf_counter() - compile_start
            specs.append(
                {
                    "name": spec["name"],
                    "description": spec["description"],
                    "runnable": runnable,
                    SURF_CONTEXT_HINT_PROVIDER_KEY: hint_provider,
                }
            )
            timings.append(
                (
                    spec["name"],
                    compile_elapsed,
                    f"compiled tools={tools_count} mw={mw_count}",
                )
            )

        total_elapsed = time.perf_counter() - loop_start
        per_subagent = ", ".join(
            f"{name}={elapsed * 1000:.0f}ms[{source}]"
            for name, elapsed, source in timings
        )
        _perf_log.info(
            "[subagent_compile] total=%.3fs count=%d details=[%s]",
            total_elapsed,
            len(timings),
            per_subagent,
        )

        return specs
