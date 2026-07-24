"""SubAgent middleware that compiles each subagent against the parent checkpointer."""

from __future__ import annotations

import time
from collections.abc import Callable
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
from langchain_core.runnables import Runnable
from langgraph.types import Checkpointer

from app.agents.chat.multi_agent_chat.subagents.shared.spec import (
    SURF_CONTEXT_HINT_PROVIDER_KEY,
    SURF_LAZY_SPEC_FACTORY_KEY,
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
        workspace_id: int | None = None,
    ) -> None:
        self._surf_checkpointer = checkpointer
        super(SubAgentMiddleware, self).__init__()
        if not subagents:
            raise ValueError(
                "At least one subagent must be specified when using the new API"
            )
        self._backend = backend
        self._subagents = subagents
        # Workspace id is captured at build time (the orchestrator runs in
        # exactly one workspace for its lifetime). The spawn-paused kill
        # switch keys on it so an operator can quarantine one workspace
        # without affecting the rest of the deployment.
        self._workspace_id = workspace_id

        # Lazy subagent compilation. Compiling a subagent graph via
        # ``create_agent`` is expensive (~250-400ms each) and there can be up
        # to ~17 of them. Doing it all in ``__init__`` put the full cost on
        # every cold ``agent_cache`` miss (i.e. on time-to-first-token), even
        # though a turn usually invokes zero or one subagent. We instead index
        # the raw specs here and compile each graph on first ``task(name)``
        # use, memoizing the result for the life of this (cached) instance.
        self._compiled: dict[str, Runnable] = {}
        self._lazy_specs: dict[str, dict[str, Any]] = {}
        # Subagents whose *spec itself* is built lazily (not just compiled).
        # Keyed by name → zero-arg factory returning the full spec dict. Used
        # for the write knowledge_base subagent, whose filesystem middleware
        # builds ~13 tool schemas (~2s) that almost never matter on turn 1.
        self._lazy_spec_factories: dict[str, Callable[[], dict[str, Any]]] = {}
        descriptors = self._build_subagent_registry()

        task_tool = build_task_tool_with_parent_config(
            descriptors,
            task_description,
            workspace_id=workspace_id,
            resolve_subagent=self._resolve_subagent,
        )
        if system_prompt and descriptors:
            agents_desc = "\n".join(
                f"- {s['name']}: {s['description']}" for s in descriptors
            )
            self.system_prompt = (
                system_prompt + "\n\nAvailable subagent types:\n" + agents_desc
            )
        else:
            self.system_prompt = system_prompt
        self.tools = [task_tool]

    def _build_subagent_registry(self) -> list[dict[str, Any]]:
        """Index subagents for lazy compilation; return lightweight descriptors.

        Pre-compiled specs (those carrying a ``runnable``) are seeded directly
        into the memo. Lazy specs are stashed by name and compiled on first
        ``task(...)`` use via :meth:`_resolve_subagent`. The returned
        descriptors carry only ``name``/``description`` plus the optional
        context-hint provider — everything the ``task`` tool needs to validate
        names, render its catalog, and run hints, without paying the
        ``create_agent`` cost up front.
        """
        descriptors: list[dict[str, Any]] = []
        for spec in self._subagents:
            # Provider may be ``None`` (no hint), in which case task_tool skips
            # the prepend step. We forward the key unconditionally so the
            # descriptor shape is uniform.
            hint_provider = cast(dict, spec).get(SURF_CONTEXT_HINT_PROVIDER_KEY)
            name = spec["name"]
            spec_factory = cast(dict, spec).get(SURF_LAZY_SPEC_FACTORY_KEY)
            if spec_factory is not None:
                # Descriptor-only entry: the spec dict is built on first use.
                self._lazy_spec_factories[name] = spec_factory
            elif "runnable" in spec:
                compiled = cast(CompiledSubAgent, spec)
                self._compiled[name] = compiled["runnable"]
            else:
                if "model" not in spec:
                    msg = f"SubAgent '{name}' must specify 'model'"
                    raise ValueError(msg)
                if "tools" not in spec:
                    msg = f"SubAgent '{name}' must specify 'tools'"
                    raise ValueError(msg)
                self._lazy_specs[name] = cast(dict, spec)
            descriptors.append(
                {
                    "name": name,
                    "description": spec["description"],
                    SURF_CONTEXT_HINT_PROVIDER_KEY: hint_provider,
                }
            )
        return descriptors

    def _resolve_subagent(self, name: str) -> Runnable:
        """Return the compiled subagent graph for ``name``, compiling on first use.

        Memoized: the ``create_agent`` cost is paid once per subagent per
        cached middleware instance. Raises ``KeyError`` for unknown names
        (callers in the ``task`` tool validate membership before resolving).
        """
        cached = self._compiled.get(name)
        if cached is not None:
            return cached
        spec = self._lazy_specs.get(name)
        if spec is None:
            factory = self._lazy_spec_factories.get(name)
            if factory is None:
                raise KeyError(name)
            # Build the spec on first use (pays the deferred construction cost
            # here, off the cold agent-build path), then compile and memoize.
            build_start = time.perf_counter()
            spec = factory()
            _perf_log.info(
                "[subagent_spec_lazy] name=%s (deferred spec build) in %.3fs",
                name,
                time.perf_counter() - build_start,
            )
        runnable = self._compile_one(spec)
        self._compiled[name] = runnable
        return runnable

    def _compile_one(self, spec: dict[str, Any]) -> Runnable:
        """Compile a single subagent graph against the parent checkpointer."""
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
        _perf_log.info(
            "[subagent_compile_lazy] name=%s in %.3fs tools=%d mw=%d",
            spec["name"],
            time.perf_counter() - compile_start,
            tools_count,
            mw_count,
        )
        return runnable
