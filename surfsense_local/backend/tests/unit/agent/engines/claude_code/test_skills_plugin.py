"""SurfSense's skills, given to Claude Code as a local plugin with its own tool names."""

import json
from pathlib import Path

import pytest

from modules.agent.engines.claude_code.skills_plugin import build_skills_plugin

pytestmark = pytest.mark.unit


def _skills(tmp_path: Path) -> Path:
    skills = tmp_path / "skills"
    (skills / "surfsense-documents" / "reference").mkdir(parents=True)
    (skills / "surfsense-documents" / "SKILL.md").write_text(
        "---\nname: surfsense-documents\n---\nCall surfsense_render_document.\n"
    )
    (skills / "surfsense-documents" / "reference" / "styles.md").write_text("Fonts.")
    return skills


def test_each_skill_is_named_under_the_surfsense_plugin(tmp_path: Path) -> None:
    """As the Skill tool names them, which is what the gate allows."""
    plugin = build_skills_plugin(_skills(tmp_path), tmp_path / "plugin")

    assert plugin.names == frozenset({"surfsense:surfsense-documents"})
    manifest = json.loads((plugin.root / ".claude-plugin" / "plugin.json").read_text())
    assert manifest["name"] == "surfsense"


def test_a_skill_names_tools_as_claude_code_sees_them(tmp_path: Path) -> None:
    """And keeps the files it points to, which the gate lets Claude Code read."""
    plugin = build_skills_plugin(_skills(tmp_path), tmp_path / "plugin")

    skill = plugin.skills / "surfsense-documents"
    assert "mcp__surfsense__render_document" in (skill / "SKILL.md").read_text()
    assert (skill / "reference" / "styles.md").read_text() == "Fonts."


def test_a_rebuild_drops_a_skill_that_is_gone(tmp_path: Path) -> None:
    """Built again at each start, from what this version ships."""
    skills = _skills(tmp_path)
    build_skills_plugin(skills, tmp_path / "plugin")
    (skills / "surfsense-documents" / "reference" / "styles.md").unlink()

    plugin = build_skills_plugin(skills, tmp_path / "plugin")

    assert not (
        plugin.skills / "surfsense-documents" / "reference" / "styles.md"
    ).exists()
