"""Guardrail C: package-relative prompt/snippet resources must resolve.

Prompt fragments are loaded by *package name* via ``importlib.resources`` — not
by import, so the import-all smoke test (guardrail A) cannot see them, and not
by mocked unit tests. A move that relocates a package without its ``.md`` files,
or that leaves a hardcoded package string stale, returns an empty string and
silently degrades the system prompt. These tests assert the resources still
resolve to non-empty content.

(Builtin skill resources are covered separately by ``test_skills_backends.py``.)
"""

from __future__ import annotations

import pytest

from app.agents.chat.multi_agent_chat.main_agent.system_prompt.builder.load_md import (
    read_prompt_md,
)
from app.agents.chat.multi_agent_chat.subagents.registry import (
    SUBAGENT_BUILDERS_BY_NAME,
    _route_resource_package,
)
from app.agents.chat.multi_agent_chat.subagents.shared.md_file_reader import (
    read_md_file,
    read_shared_snippet,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("name", sorted(SUBAGENT_BUILDERS_BY_NAME))
def test_every_subagent_has_description_md(name: str):
    """Each specialist ships a non-empty ``description.md`` next to its agent."""
    package = _route_resource_package(SUBAGENT_BUILDERS_BY_NAME[name])
    assert read_md_file(package, "description").strip(), (
        f"{name}: description.md missing/empty at package {package}"
    )


# Real fragments under the hardcoded main-agent prompts package, including a
# nested path — guards both the package string and nested resource resolution.
@pytest.mark.parametrize(
    "filename",
    [
        "core_behavior.md",
        "routing.md",
        "tools/web_search/description.md",
    ],
)
def test_main_agent_prompt_fragments_resolve(filename: str):
    """Main-agent prompt fragments resolve to non-empty content."""
    assert read_prompt_md(filename).strip(), f"prompt fragment {filename} is empty"


@pytest.mark.parametrize("snippet", ["output_contract_base", "verifiable_handle"])
def test_shared_snippets_resolve(snippet: str):
    """Shared subagent snippets resolve from the snippets package."""
    assert read_shared_snippet(snippet).strip(), f"snippet {snippet} is empty"
