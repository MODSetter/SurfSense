"""Guardrail A: every agent module (and its prod entrypoints) must import.

Static reachability analysis and mocked unit tests cannot catch a module that
fails to import after files move or imports are rewritten. This smoke test
imports every submodule under ``app.agents`` plus the production entrypoints
that consume agents, turning a move-time ``ImportError`` into a fast, local CI
signal instead of a runtime failure in prod.
"""

from __future__ import annotations

import importlib
import pkgutil

import pytest

import app.agents as agents_pkg

pytestmark = pytest.mark.unit

# Prod consumers of app.agents that live OUTSIDE the agents tree; a broken
# importer here would not be caught by walking app.agents alone.
_PROD_ENTRYPOINTS = [
    "app.tasks.chat.streaming.flows.new_chat.orchestrator",
    "app.tasks.chat.streaming.agent.builder",
    "app.gateway.agent_invoke",
    "app.routes.new_chat_routes",
]


def _iter_agent_modules() -> list[str]:
    names: list[str] = []

    def _record(name: str) -> None:
        names.append(name)

    for info in pkgutil.walk_packages(
        agents_pkg.__path__, prefix=agents_pkg.__name__ + ".", onerror=_record
    ):
        names.append(info.name)
    return sorted(set(names))


@pytest.mark.parametrize("module_name", _iter_agent_modules())
def test_agent_module_imports(module_name: str) -> None:
    """Importing the module must not raise (no broken or missed imports)."""
    importlib.import_module(module_name)


@pytest.mark.parametrize("module_name", _PROD_ENTRYPOINTS)
def test_prod_entrypoint_imports(module_name: str) -> None:
    """The production code paths that build/invoke agents must import."""
    importlib.import_module(module_name)
