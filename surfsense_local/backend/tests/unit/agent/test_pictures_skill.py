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


def _script(pages: list[tuple[str, list[str]]]) -> str:
    """The script the skill gives, filled as the agent fills it."""
    (script,) = re.findall(r"```python\n(.*?)```", _file("pdf.md"), re.S)
    filled = re.sub(
        r"PAGES = \[\n.*?\n\]", f"PAGES = {pages!r}", script, count=1, flags=re.S
    )
    assert filled != script
    return filled


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
