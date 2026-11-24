"""The pictures skill as the agent reads it."""

import re
from pathlib import Path

import pytest

from modules.agent.engines.claude_code.skills_plugin import build_skills_plugin
from modules.agent.opencode_config import PICTURES_SKILL, skills_folder
from modules.agent.tool_endpoint.make_image import LISTING

pytestmark = pytest.mark.unit


def _file(name: str) -> str:
    return (skills_folder() / PICTURES_SKILL / name).read_text(encoding="utf-8")


def test_the_skill_names_itself_as_opencode_finds_it() -> None:
    """opencode lists a skill by its frontmatter name, and the config allows only that one."""
    frontmatter = _file("SKILL.md").split("---")[1]

    assert f"name: {PICTURES_SKILL}\n" in frontmatter
    assert "comic" in frontmatter


def test_the_tool_sends_a_set_of_pictures_to_the_skill() -> None:
    """The prompt is full, so the tool's description names the skill too."""
    assert f"load the {PICTURES_SKILL} skill first" in LISTING["description"]


def test_the_skill_never_sends_the_user_to_settings() -> None:
    """A model that takes no picture in is said plainly, never set up mid-comic."""
    for name in ("SKILL.md", "comics.md"):
        # The app writes the path with a chevron; the agent's prompts with ">".
        assert "Settings \u203a" not in _file(name), name
        assert "Settings >" not in _file(name), name


def test_a_claude_plan_thread_gets_the_skill_with_its_own_tool_names(
    tmp_path: Path,
) -> None:
    """Claude Code reads the same skill, its SurfSense tools named as it lists them."""
    plugin = build_skills_plugin(skills_folder(), tmp_path / "plugin")

    assert f"surfsense:{PICTURES_SKILL}" in plugin.names
    for name in ("SKILL.md", "comics.md"):
        text = (plugin.skills / PICTURES_SKILL / name).read_text(encoding="utf-8")
        assert not re.search(
            r"surfsense_(make_image|bind_comic|render_document|read_document)", text
        )
    skill = (plugin.skills / PICTURES_SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert "mcp__surfsense__make_image" in skill


def test_comics_cover_every_kind_the_user_may_ask_for() -> None:
    """Each reads and is laid out its own way; a manga is not a Western comic."""
    comics = _file("comics.md").lower()

    for kind in (
        "manga",
        "manhwa",
        "webtoon",
        "manhua",
        "comic strip",
        "yonkoma",
        "graphic novel",
        "bande dessinée",
        "picture book",
        "storyboard",
    ):
        assert kind in comics, kind


def test_a_comic_is_bound_by_its_own_tool_not_a_script() -> None:
    """The binder is the app's; the agent no longer copies a script to fill."""
    assert not (skills_folder() / PICTURES_SKILL / "pdf.md").exists()
    for name in ("SKILL.md", "comics.md"):
        text = _file(name)
        assert "surfsense_bind_comic" in text, name
        assert "surfsense_render_document" not in text, name


def test_a_comics_pages_are_drawn_as_its_pages() -> None:
    """Marked from the first, a page is never listed in Studio apart from its comic."""
    assert "comic_page: true" in _file("SKILL.md")
