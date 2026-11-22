"""SurfSense's skills as a Claude Code plugin, `surfsense`, naming tools as Claude Code lists them.

The skills are written for opencode, which calls SurfSense's tools
`surfsense_<tool>`; Claude Code calls them `mcp__surfsense__<tool>`.
"""

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from modules.agent.engines.claude_code.tool_names import for_claude

PLUGIN = "surfsense"


@dataclass(frozen=True)
class SkillsPlugin:
    root: Path
    # Where each skill's files are, which the gate lets Claude Code read.
    skills: Path
    # As the Skill tool names them: `surfsense:surfsense-documents`.
    names: frozenset[str]


def build_skills_plugin(skills: Path, target: Path) -> SkillsPlugin:
    """Rebuilt whole from the shipped skills; built at start, before any turn reads it."""
    fresh = target.with_name(f"{target.name}.new")
    shutil.rmtree(fresh, ignore_errors=True)
    shutil.copytree(skills, fresh / "skills")
    for markdown in (fresh / "skills").rglob("*.md"):
        markdown.write_text(
            for_claude(markdown.read_text(encoding="utf-8")), encoding="utf-8"
        )
    (fresh / ".claude-plugin").mkdir()
    (fresh / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": PLUGIN, "description": "SurfSense's skills"})
    )
    shutil.rmtree(target, ignore_errors=True)
    fresh.rename(target)
    names = frozenset(
        f"{PLUGIN}:{skill.name}"
        for skill in (target / "skills").iterdir()
        if (skill / "SKILL.md").is_file()
    )
    return SkillsPlugin(target, target / "skills", names)
