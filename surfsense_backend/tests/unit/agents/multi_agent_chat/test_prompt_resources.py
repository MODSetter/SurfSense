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
    main_prompt_registry_subagent_lines,
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


def test_deliverables_roster_advertises_file_artifacts():
    """The supervisor must route explicit PDF, Word, and PowerPoint requests."""
    description = dict(main_prompt_registry_subagent_lines([]))["deliverables"]

    assert all(
        marker in description
        for marker in ("PDF", "Word", "DOCX", ".docx", "PowerPoint", "PPTX", ".pptx")
    )
    assert all(marker in description for marker in ("mind maps", "static PNG"))


def test_presentation_routing_separates_pptx_from_video():
    """PPTX artifacts and video media have independent routing contracts."""
    routing = read_prompt_md("routing.md")
    deliverables_package = _route_resource_package(
        SUBAGENT_BUILDERS_BY_NAME["deliverables"]
    )
    deliverables_prompt = read_md_file(deliverables_package, "system_prompt")

    assert "**PPTX artifacts.**" in routing
    assert "editable PPTX artifact" in routing
    assert "**Video media.**" in routing
    assert "narrated audiovisual output" in deliverables_prompt


def test_reports_and_resumes_default_to_pdf_without_format_clarification():
    """Supervisor and specialist apply the canonical artifact format policy."""
    routing = read_prompt_md("routing.md")
    task_description = read_prompt_md("tools/task/description.md")
    deliverables_package = _route_resource_package(
        SUBAGENT_BUILDERS_BY_NAME["deliverables"]
    )
    deliverables_prompt = read_md_file(deliverables_package, "system_prompt")

    assert "**Report and resume artifacts.**" in routing
    assert "create a PDF artifact" in routing
    assert "rather than asking follow-up questions or drafting the" in routing
    assert 'brief follow-ups such as "just do it" preserve this intent' in routing
    assert "including any required artifact format" in task_description
    assert "Choose the output format from the user's intent without asking" in (
        deliverables_prompt
    )
    assert "Reports, resumes/CVs, printable documents, letters, and one-pagers" in (
        deliverables_prompt
    )
    assert "An omitted format is never a missing constraint" in deliverables_prompt
    assert "rather than substituting" in deliverables_prompt
    assert "a Markdown-only artifact or an inline draft" in deliverables_prompt
    assert (
        '"artifact_type": "artifact" | "podcast" | "video_presentation" | "deliverable_job" | "image"'
        in deliverables_prompt
    )
    assert 'Files saved through `save_artifact` use `type="artifact"`' in (
        deliverables_prompt
    )


def test_file_deliverable_revisions_are_in_place():
    """Supervisor and specialist must preserve an artifact's document ID."""
    routing = read_prompt_md("routing.md")
    deliverables_package = _route_resource_package(
        SUBAGENT_BUILDERS_BY_NAME["deliverables"]
    )
    deliverables_prompt = read_md_file(deliverables_package, "system_prompt")

    assert "**File-deliverable revisions are in place.**" in routing
    assert "do not invent versioning as a safety measure" in routing
    assert "then call `save_artifact` with that same `artifact_id`" in (
        deliverables_prompt
    )
    assert "a changed title, filename,\n  or design does not create" in (
        deliverables_prompt
    )
    assert "change visual style" in routing
    assert "Do not list infographic style presets in chat" in routing
    assert "`change_infographic_style=True` only if they asked" in deliverables_prompt


def test_failed_verification_cannot_advance_to_save():
    """The specialist must treat verification as a publication gate."""
    deliverables_package = _route_resource_package(
        SUBAGENT_BUILDERS_BY_NAME["deliverables"]
    )
    deliverables_prompt = read_md_file(deliverables_package, "system_prompt")

    assert "Treat verification as a state transition, not advice." in (
        deliverables_prompt
    )
    assert "stop without calling `save_artifact`" in deliverables_prompt
    assert (
        "Treat visual suggestions and placeholders as design direction, not visible"
        in deliverables_prompt
    )


# Real fragments under the hardcoded main-agent prompts package, including a
# nested path — guards both the package string and nested resource resolution.
@pytest.mark.parametrize(
    "filename",
    [
        "core_behavior.md",
        "routing.md",
        "tools/task/description.md",
    ],
)
def test_main_agent_prompt_fragments_resolve(filename: str):
    """Main-agent prompt fragments resolve to non-empty content."""
    assert read_prompt_md(filename).strip(), f"prompt fragment {filename} is empty"


def test_core_omits_routine_tool_narration_without_suppressing_reasoning():
    core = read_prompt_md("core_behavior.md")
    anthropic = read_prompt_md("providers/anthropic.md")

    assert "Omit routine user-visible narration" in core
    assert "does not constrain internal or\n  provider-native reasoning" in core
    assert "Structured reasoning:" in anthropic
    assert "`<thinking>` / short `<plan>` before tool calls is fine" in anthropic


@pytest.mark.parametrize("snippet", ["output_contract_base", "verifiable_handle"])
def test_shared_snippets_resolve(snippet: str):
    """Shared subagent snippets resolve from the snippets package."""
    assert read_shared_snippet(snippet).strip(), f"snippet {snippet} is empty"
