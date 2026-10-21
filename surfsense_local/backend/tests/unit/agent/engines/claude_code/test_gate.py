"""The rules Claude Code's tool calls meet: opencode's, for the same thread."""

from pathlib import Path

import pytest

from modules.agent.engines.claude_code.gate import Gate

pytestmark = pytest.mark.unit


@pytest.fixture
def gate(tmp_path: Path) -> Gate:
    """Thread 7's rules, with one plugin's tools given: one allowed, one to ask."""
    folder = tmp_path / "threads" / "7"
    (folder / "sources").mkdir(parents=True)
    (folder / "outputs").mkdir()
    skills = tmp_path / "skills"
    (skills / "surfsense-documents").mkdir(parents=True)
    return Gate(
        folder=folder,
        skills=skills,
        skill_names=frozenset({"surfsense:surfsense-documents"}),
        plugin_rules={
            "mcp__notion__search": "allow",
            "mcp__notion__create_page": "ask",
        },
    )


def test_reads_inside_the_thread_folder_are_allowed(gate: Gate) -> None:
    """Relative paths are the thread folder's, as Claude Code's working folder."""
    assert gate.decide("Read", {"file_path": "sources/plan.txt"}).action == "allow"
    absolute = str(gate.folder / "outputs" / "q3.md")
    assert gate.decide("Read", {"file_path": absolute}).action == "allow"
    assert gate.decide("Glob", {"pattern": "sources/**/*.md"}).action == "allow"
    assert gate.decide("Grep", {"pattern": "revenue", "path": "sources"}).action == (
        "allow"
    )
    # With no path, Glob and Grep search the working folder, the thread's.
    assert gate.decide("Grep", {"pattern": "revenue"}).action == "allow"


def test_a_skill_may_point_into_the_skills_folder(gate: Gate) -> None:
    """As opencode's external_directory rule allows the skills folder alone."""
    guide = str(gate.skills / "surfsense-documents" / "SKILL.md")

    assert gate.decide("Read", {"file_path": guide}).action == "allow"


def test_reads_outside_the_thread_are_refused_with_a_reason(gate: Gate) -> None:
    """Another thread's folder included; the reason reaches the model."""
    for tool, tool_input in [
        ("Read", {"file_path": "/etc/hosts"}),
        ("Read", {"file_path": "../8/sources/secret.txt"}),
        ("Read", {"file_path": str(gate.skills / ".." / "elsewhere.txt")}),
        ("Glob", {"pattern": "../**/*"}),
        ("Glob", {"pattern": "*.md", "path": "/Users"}),
        ("Grep", {"pattern": "x", "path": ".."}),
    ]:
        verdict = gate.decide(tool, tool_input)
        assert verdict.action == "deny", (tool, tool_input)
        assert verdict.reason


def test_a_link_out_of_the_folder_is_followed_before_it_is_judged(
    gate: Gate, tmp_path: Path
) -> None:
    """A path is compared once symlinks are resolved, so a link cannot smuggle a read."""
    (tmp_path / "private.txt").write_text("no")
    (gate.folder / "outputs" / "link.txt").symlink_to(tmp_path / "private.txt")

    assert gate.decide("Read", {"file_path": "outputs/link.txt"}).action == "deny"


def test_writes_go_only_under_outputs(gate: Gate) -> None:
    """Sources, the folder's root, other threads and the skills stay untouched."""
    assert gate.decide("Write", {"file_path": "outputs/q3.md"}).action == "allow"
    nested = str(gate.folder / "outputs" / "drafts" / "q3.md")
    assert gate.decide("Edit", {"file_path": nested}).action == "allow"
    for path in [
        "sources/plan.txt",
        "notes.md",
        "../8/outputs/q3.md",
        "/tmp/escaped.txt",
        str(gate.skills / "surfsense-documents" / "SKILL.md"),
    ]:
        verdict = gate.decide("Write", {"file_path": path})
        assert verdict.action == "deny", path
        assert verdict.reason


def test_files_an_agent_reads_as_instructions_are_never_written(gate: Gate) -> None:
    """opencode refuses these in any case on macOS too, where names ignore case."""
    for name in ["AGENTS.md", "claude.md", "Context.md", ".claude/settings.json"]:
        verdict = gate.decide("Write", {"file_path": f"outputs/{name}"})
        assert verdict.action == "deny", name


def test_a_link_from_outputs_into_sources_cannot_be_written_through(
    gate: Gate,
) -> None:
    """A source edited through a link would change what every thread reads."""
    (gate.folder / "sources" / "plan.txt").write_text("source")
    (gate.folder / "outputs" / "plan.txt").symlink_to(
        gate.folder / "sources" / "plan.txt"
    )

    assert gate.decide("Edit", {"file_path": "outputs/plan.txt"}).action == "deny"


def test_only_surfsenses_own_skills_load(gate: Gate) -> None:
    """Claude Code's built-in skills and the user's own are refused."""
    assert gate.decide("Skill", {"skill": "surfsense:surfsense-documents"}).action == (
        "allow"
    )
    for name in ["deep-research", "code-review", "surfsense:other"]:
        assert gate.decide("Skill", {"skill": name}).action == "deny", name


def test_surfsenses_tools_are_allowed(gate: Gate) -> None:
    """Each refuses on its own what a turn may not do, as it does for opencode."""
    assert gate.decide("mcp__surfsense__search_sources", {"query": "q3"}).action == (
        "allow"
    )


def test_a_plugin_tool_follows_its_rule_and_any_other_is_refused(gate: Gate) -> None:
    """The rules are the gateway's, as opencode's session rules are."""
    assert gate.decide("mcp__notion__search", {}).action == "allow"
    assert gate.decide("mcp__notion__create_page", {}).action == "ask"
    # Switched off, unreviewed, or on a server not given this turn.
    assert gate.decide("mcp__notion__delete_page", {}).action == "deny"
    assert gate.decide("mcp__github__create_issue", {}).action == "deny"


def test_tools_surfsense_never_gives_are_refused(gate: Gate) -> None:
    """Even if a later Claude Code offered them unasked."""
    for tool in ["Bash", "WebFetch", "WebSearch", "Task", "NotebookEdit", "Monitor"]:
        verdict = gate.decide(tool, {})
        assert verdict.action == "deny", tool
        assert verdict.reason


def test_a_long_result_claude_code_saved_for_this_session_can_be_read(
    tmp_path: Path,
) -> None:
    """Claude Code saves a large tool result and tells the model to read it there,
    as opencode does with its tool-output folder."""
    home = tmp_path / "claude-home"
    saved = home / "projects" / "-threads-7" / "session-7" / "tool-results"
    saved.mkdir(parents=True)
    (saved / "toolu_1.txt").write_text("{}")
    gate = Gate(
        folder=tmp_path / "threads" / "7",
        skills=tmp_path / "skills",
        claude_home=home,
        session_id="session-7",
    )

    assert gate.decide("Read", {"file_path": str(saved / "toolu_1.txt")}).action == (
        "allow"
    )
    assert gate.decide("Grep", {"pattern": "title", "path": str(saved)}).action == (
        "allow"
    )


def test_only_this_sessions_saved_results_and_never_to_write(tmp_path: Path) -> None:
    """Not another session's results, nor Claude Code's own settings and sign-in."""
    home = tmp_path / "claude-home"
    gate = Gate(
        folder=tmp_path / "threads" / "7",
        skills=tmp_path / "skills",
        claude_home=home,
        session_id="session-7",
    )
    projects = home / "projects" / "-threads-7"

    for path in [
        projects / "session-8" / "tool-results" / "toolu_1.txt",
        projects / "session-7.jsonl",
        projects / "session-7" / "subagents" / "x.txt",
        home / "settings.json",
        home / ".credentials.json",
    ]:
        assert gate.decide("Read", {"file_path": str(path)}).action == "deny", path
    saved = projects / "session-7" / "tool-results" / "toolu_1.txt"
    assert gate.decide("Write", {"file_path": str(saved)}).action == "deny"
