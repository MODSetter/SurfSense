"""Claude Code's tool names and opencode's, for the same tool."""

import pytest

from modules.agent.engines.claude_code.tool_names import (
    claude_tool,
    for_claude,
    step_input,
    step_tool,
)

pytestmark = pytest.mark.unit


def test_a_step_is_named_as_opencode_names_it_so_the_thread_labels_it_alike() -> None:
    """The frontend labels steps, and opens versions, by opencode's names."""
    assert step_tool("Read") == "read"
    assert step_tool("Glob") == "glob"
    assert step_tool("Edit") == "edit"
    assert step_tool("mcp__surfsense__render_document") == "surfsense_render_document"
    assert step_tool("mcp__notion__create_page") == "notion_create_page"


def test_a_plugin_tool_is_named_as_claude_code_names_it() -> None:
    """Claude Code turns anything but letters, digits, _ and - into _, as opencode does."""
    assert claude_tool("notion", "create_page") == "mcp__notion__create_page"
    assert claude_tool("my plugin", "do.thing/now") == "mcp__my_plugin__do_thing_now"


def test_a_steps_input_uses_opencodes_keys() -> None:
    """The label reads `path`; Claude Code's file tools send `file_path`."""
    assert step_input("Edit", {"file_path": "outputs/a.md", "old_string": "x"}) == {
        "path": "outputs/a.md",
        "oldString": "x",
    }
    assert step_input("mcp__surfsense__search_sources", {"query_text": "q"}) == {
        "query_text": "q"
    }


def test_the_skills_name_surfsenses_tools_as_claude_code_sees_them() -> None:
    """Written for opencode, the skills and prompt are given to Claude Code renamed."""
    text = (
        "Call surfsense_render_document, then surfsense_read_document. "
        "The surfsense-documents skill, and surfsense_nothing, stay as they are."
    )

    assert for_claude(text) == (
        "Call mcp__surfsense__render_document, then mcp__surfsense__read_document. "
        "The surfsense-documents skill, and surfsense_nothing, stay as they are."
    )


def test_the_file_tools_a_note_names_are_claude_codes() -> None:
    """opencode's `read`, `grep` and `glob` are Claude Code's Read, Grep and Glob."""
    text = "Open them with `read`, or search with `grep` and `glob`; reading stays."

    assert for_claude(text) == (
        "Open them with `Read`, or search with `Grep` and `Glob`; reading stays."
    )
