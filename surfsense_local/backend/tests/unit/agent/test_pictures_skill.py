"""The pictures skill as the agent reads it, and its binding script as a render
runs it: alone, from an empty folder, with the pictures named in IMAGES_DIR."""

import io
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image
from pypdf import PdfReader

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
    for name in ("SKILL.md", "comics.md", "pdf.md"):
        # The app writes the path with a chevron; the agent's prompts with ">".
        assert "Settings \u203a" not in _file(name), name
        assert "Settings >" not in _file(name), name


def test_a_claude_plan_thread_gets_the_skill_with_its_own_tool_names(
    tmp_path: Path,
) -> None:
    """Claude Code reads the same skill, its SurfSense tools named as it lists them."""
    plugin = build_skills_plugin(skills_folder(), tmp_path / "plugin")

    assert f"surfsense:{PICTURES_SKILL}" in plugin.names
    for name in ("SKILL.md", "comics.md", "pdf.md"):
        text = (plugin.skills / PICTURES_SKILL / name).read_text(encoding="utf-8")
        assert not re.search(
            r"surfsense_(make_image|render_document|read_document)", text
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


def _script(
    pages: list[tuple[str, list[str]]],
    direction: str = "ltr",
    layout: str = "pages",
) -> str:
    """The script the skill gives, filled as the agent fills it."""
    (script,) = re.findall(r"```python\n(.*?)```", _file("pdf.md"), re.S)
    filled = re.sub(
        r"PAGES = \[\n.*?\n\]", f"PAGES = {pages!r}", script, count=1, flags=re.S
    )
    filled = filled.replace('DIRECTION = "ltr"', f"DIRECTION = {direction!r}", 1)
    filled = filled.replace('LAYOUT = "pages"', f"LAYOUT = {layout!r}", 1)
    assert filled != script
    assert f"DIRECTION = {direction!r}" in filled
    assert f"LAYOUT = {layout!r}" in filled
    return filled


def _bind(tmp_path: Path, script: str, count: int) -> PdfReader:
    images, work = tmp_path / "images", tmp_path / "work"
    images.mkdir()
    work.mkdir()
    # A colour each: ReportLab stores one copy of pictures that are the same.
    for n, colour in zip(
        range(1, count + 1), ("red", "green", "blue", "white"), strict=False
    ):
        (images / f"image-{n}.png").write_bytes(_page(colour, (1024, 1536)))
    output = tmp_path / "comic.pdf"
    subprocess.run(
        [sys.executable, "-c", script],
        cwd=work,
        env={**os.environ, "OUTPUT_PATH": str(output), "IMAGES_DIR": str(images)},
        check=True,
    )
    return PdfReader(output)


def test_a_manga_reads_right_to_left(tmp_path: Path) -> None:
    """A reader then lays its spreads out as a manga's are."""
    pages = [(f"image-{n}", []) for n in range(1, 3)]

    pdf = _bind(tmp_path, _script(pages, direction="rtl"), 2)

    assert pdf.trailer["/Root"]["/ViewerPreferences"]["/Direction"] == "/R2L"
    assert len(pdf.pages) == 2


def test_a_webtoon_scrolls_down_one_long_page(tmp_path: Path) -> None:
    """Its panels stack in one column, read by scrolling, not page by page."""
    pages = [(f"image-{n}", []) for n in range(1, 4)]

    pdf = _bind(tmp_path, _script(pages, layout="scroll"), 3)

    (page,) = pdf.pages
    assert len(page.images) == 3
    width, height = float(page.mediabox.width), float(page.mediabox.height)
    assert height > 3 * width * 1.5


def _page(colour: str, size: tuple[int, int]) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", size, colour).save(out, "PNG")
    return out.getvalue()


def test_the_pages_are_bound_one_a_page_as_jpeg(tmp_path: Path) -> None:
    """Four comic pages in a PDF of a few megabytes, not the tens PNG made."""
    images, work = tmp_path / "images", tmp_path / "work"
    images.mkdir()
    work.mkdir()
    noisy = Image.effect_noise((1024, 1536), 64).convert("RGB")
    for n in range(1, 5):
        out = io.BytesIO()
        noisy.save(out, "PNG")
        (images / f"image-{n}.png").write_bytes(out.getvalue())
    output = tmp_path / "comic.pdf"

    subprocess.run(
        [sys.executable, "-c", _script([(f"image-{n}", []) for n in range(1, 5)])],
        cwd=work,
        env={**os.environ, "OUTPUT_PATH": str(output), "IMAGES_DIR": str(images)},
        check=True,
    )

    pdf = PdfReader(output)
    assert len(pdf.pages) == 4
    for page in pdf.pages:
        (picture,) = page.images
        assert picture.name.endswith(".jpg"), picture.name
    assert output.stat().st_size < 5 * 1024 * 1024


def test_a_page_with_lines_gets_them_exactly_in_a_strip_below(tmp_path: Path) -> None:
    """A page whose lettering came out wrong keeps the exact words, unredrawn."""
    images, work = tmp_path / "images", tmp_path / "work"
    images.mkdir()
    work.mkdir()
    (images / "image-1.png").write_bytes(_page("white", (1024, 1536)))
    (images / "image-2.png").write_bytes(_page("white", (1024, 1536)))
    output = tmp_path / "comic.pdf"
    said = "NORA: The bulb is broken!"

    subprocess.run(
        [sys.executable, "-c", _script([("image-1", []), ("image-2", [said])])],
        cwd=work,
        env={**os.environ, "OUTPUT_PATH": str(output), "IMAGES_DIR": str(images)},
        check=True,
    )

    plain, lettered = PdfReader(output).pages
    assert said in lettered.extract_text()
    assert said not in plain.extract_text()
    assert float(lettered.mediabox.height) > float(plain.mediabox.height)
    assert float(lettered.mediabox.width) == float(plain.mediabox.width)
