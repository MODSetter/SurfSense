"""What Claude Code may do in a thread: opencode's permission rules, applied to Claude Code's tool names.

docs/architecture/claude-plan.md, The gate.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path, PurePath
from typing import Any, Literal

from modules.agent.engines.claude_code.saved_results import is_saved_result

Action = Literal["allow", "ask", "deny"]

_READING = {"Read": "file_path", "Glob": "path", "Grep": "path"}
_WRITING = frozenset({"Write", "Edit"})
# Read as instructions by an agent; casefolded, as macOS matches names.
_INSTRUCTION_FILES = frozenset({"agents.md", "claude.md", "context.md"})
_INSTRUCTION_FOLDERS = frozenset({".claude", ".opencode"})
# SurfSense's own tools, on the thread's tool endpoint.
_SURFSENSE_TOOLS = "mcp__surfsense__"
_GLOB_CHARACTERS = frozenset("*?[{")
_OUTSIDE = "Only files in this thread's folder can be read."
_NOT_OUTPUTS = "Files can be written only under this thread's outputs/ folder."


@dataclass(frozen=True)
class Verdict:
    action: Action
    # Given to the model when a call is refused, so it can work around it.
    reason: str = ""


@dataclass(frozen=True)
class Gate:
    """The rules for one thread's turn: its folder, the skills folder a skill may
    point into, SurfSense's skills, and each given plugin tool's rule."""

    folder: Path
    skills: Path
    skill_names: frozenset[str] = frozenset()
    # By Claude Code's name for the tool; a plugin tool absent here is denied.
    plugin_rules: Mapping[str, Action] = field(default_factory=dict)
    # Where Claude Code saved this session's long tool results, readable alone.
    claude_home: Path | None = None
    session_id: str | None = None

    def decide(self, tool: str, tool_input: dict[str, Any]) -> Verdict:
        if tool in _READING:
            return self._read(tool, tool_input)
        if tool in _WRITING:
            return self._write(tool_input.get("file_path") or "")
        if tool == "Skill":
            if tool_input.get("skill") in self.skill_names:
                return Verdict("allow")
            return Verdict("deny", "Only SurfSense's skills can be used here.")
        if tool.startswith(_SURFSENSE_TOOLS):
            return Verdict("allow")
        if tool in self.plugin_rules:
            return Verdict(self.plugin_rules[tool])
        return Verdict("deny", f"{tool} is not available in SurfSense.")

    def _read(self, tool: str, tool_input: dict[str, Any]) -> Verdict:
        base = self._resolve(tool_input.get(_READING[tool]) or ".")
        if not self._readable(base):
            return Verdict("deny", _OUTSIDE)
        if tool == "Glob" and not self._pattern_stays_in(
            base, tool_input.get("pattern") or ""
        ):
            return Verdict("deny", _OUTSIDE)
        return Verdict("allow")

    def _write(self, path: str) -> Verdict:
        target = self._resolve(path)
        outputs = (self.folder / "outputs").resolve()
        if not target.is_relative_to(outputs):
            return Verdict("deny", _NOT_OUTPUTS)
        names = {part.casefold() for part in target.relative_to(outputs).parts}
        if names & _INSTRUCTION_FOLDERS or target.name.casefold() in _INSTRUCTION_FILES:
            return Verdict("deny", f"{target.name} cannot be written in SurfSense.")
        return Verdict("allow")

    def _resolve(self, path: str) -> Path:
        """Relative to the thread's folder, as Claude Code's working folder; links followed."""
        return (self.folder / path).resolve()

    def _readable(self, path: Path) -> bool:
        if path.is_relative_to(self.folder.resolve()) or path.is_relative_to(
            self.skills.resolve()
        ):
            return True
        return (
            self.claude_home is not None
            and self.session_id is not None
            and is_saved_result(path, self.claude_home, self.session_id)
        )

    def _pattern_stays_in(self, base: Path, pattern: str) -> bool:
        """The part of a pattern before its first wildcard names a folder, which must be readable."""
        parts = PurePath(pattern).parts
        if ".." in parts:
            return False
        literal = []
        for part in parts:
            if _GLOB_CHARACTERS & set(part):
                break
            literal.append(part)
        return self._readable((base / Path(*literal)).resolve()) if literal else True
