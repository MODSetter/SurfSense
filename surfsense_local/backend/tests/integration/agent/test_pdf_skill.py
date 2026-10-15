"""The PDF skill as the agent reads it: the tools it names exist, and its ranges parse as it says."""

import re

import pytest

from modules.agent.opencode_config import PDF_SKILL, skills_folder
from modules.agent.tool_endpoint.offered_tools import TOOLS
from modules.agent.tool_endpoint.registration import SERVER
from modules.pdf_tools.page_ranges import page_groups, page_numbers

pytestmark = pytest.mark.integration


def _skill() -> str:
    return (skills_folder() / PDF_SKILL / "SKILL.md").read_text(encoding="utf-8")


def test_the_skill_names_itself_as_opencode_finds_it() -> None:
    """opencode lists a skill by its frontmatter name, and the config allows only that one."""
    frontmatter = _skill().split("---")[1]

    assert f"name: {PDF_SKILL}\n" in frontmatter
    assert "description: " in frontmatter


def test_every_tool_the_skill_names_is_offered() -> None:
    """A renamed tool would leave the skill sending the model to one that is gone."""
    named = set(re.findall(rf"`{SERVER}_(\w+)`", _skill()))

    assert {"pdf_pages", "pdf_stamp", "pdf_form"} <= named
    assert named <= set(TOOLS)


def test_the_ranges_the_skill_shows_mean_what_it_says() -> None:
    """The model copies the examples, so each must parse to the pages the skill names."""
    assert page_numbers("1-3,7", 10) == [1, 2, 3, 7]
    assert page_numbers("5-", 7) == [5, 6, 7]
    assert page_numbers("9-7", 9) == [9, 8, 7]
    assert len(page_groups("1-4,5-9,10-", 12)) == 3
    for written in ("1-3,7", "5-", "9-7", "1-4,5-9,10-", "3,1,2", "2-"):
        assert f'`"{written}"`' in _skill()


def test_the_skill_says_the_users_pdf_is_never_changed() -> None:
    """Users ask whether their original is safe; the model must know it is."""
    text = _skill()

    assert "the user's own file stays exactly as it was" in text
    assert "List the fields first" in text
    assert "XFA" in text
