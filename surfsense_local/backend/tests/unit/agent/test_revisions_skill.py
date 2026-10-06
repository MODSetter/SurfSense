"""The revisions skill as the agent reads it: found by its name, and holding the rules the tool enforces."""

import pytest

from modules.agent.opencode_config import REVISIONS_SKILL, skills_folder
from modules.agent.tool_endpoint.revise_document import LISTING, OPERATIONS

pytestmark = pytest.mark.unit


def _skill() -> str:
    return (skills_folder() / REVISIONS_SKILL / "SKILL.md").read_text(encoding="utf-8")


def test_the_skill_names_itself_as_opencode_finds_it() -> None:
    """opencode lists a skill by its frontmatter name, and the config allows only that one."""
    frontmatter = _skill().split("---")[1]

    assert f"name: {REVISIONS_SKILL}\n" in frontmatter
    assert "description: " in frontmatter


def test_the_tool_sends_the_model_to_the_skill() -> None:
    """The prompt is full, so the tool's description is what names the skill."""
    assert f"Load the {REVISIONS_SKILL} skill first." in LISTING["description"]


def test_the_skill_teaches_every_operation_the_tool_takes() -> None:
    """An operation the skill never names is one the model guesses at."""
    text = _skill()

    for op in OPERATIONS:
        assert f"`{op}`" in text, op


def test_the_skill_says_word_edits_are_always_tracked_and_the_file_is_untouched() -> (
    None
):
    """Decisions 11 and 12: the model must never tell the user a change is final."""
    text = _skill()

    assert "There is no way to edit without tracking" in text
    assert "Their file is never changed" in text
    assert "`artifact_id`" in text and "`document_id`" in text


def test_a_workbook_s_cells_are_read_before_it_is_revised() -> None:
    """Indexed text has no sheet names, addresses or formulas, so a guessed set_cell lands wrong."""
    text = _skill()

    assert (
        "For a workbook, first read its cells with surfsense_read_document"
        in LISTING["description"]
    )
    assert "`surfsense_read_document` with its `document_id`" in text
