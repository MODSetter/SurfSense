"""The HTML skill's figure examples: complete pages the agent can start from as they are."""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from modules.agent.opencode_config import skills_folder
from modules.agent.tool_endpoint.save_page import PAGE_BYTES
from modules.artifacts.web_pages.outside_resources import outside_resources
from modules.artifacts.web_pages.page_checks import checked_page

pytestmark = pytest.mark.unit

SKILL = skills_folder() / "surfsense-html"
EXAMPLES = sorted((SKILL / "examples").glob("*.md"))
FENCED = re.compile(r"```(\w+)\n(.*?)\n```", re.DOTALL)


def _block(path: Path, language: str) -> str:
    (block,) = [
        code for lang, code in FENCED.findall(path.read_text()) if lang == language
    ]
    return block


def test_there_is_an_example_for_each_kind_of_mechanism_figures_md_names() -> None:
    """figures.md sends the agent to these files by name."""
    named = set(
        re.findall(r"examples/([\w-]+\.md)", (SKILL / "figures.md").read_text())
    )
    assert named == {path.name for path in EXAMPLES}
    assert len(EXAMPLES) == 3


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda p: p.stem)
def test_each_example_is_a_page_save_page_keeps_and_loads_nothing(
    example: Path,
) -> None:
    """A whole document, under the size limit, with no request the viewer would block."""
    page = _block(example, "html")
    assert page.startswith("<!doctype html>")
    checked_page(page.encode("utf-8"), PAGE_BYTES)
    assert outside_resources(page) == []
    assert "prefers-color-scheme: dark" not in page


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda p: p.stem)
def test_each_example_carries_the_helper_exactly_as_isometric_md_gives_it(
    example: Path,
) -> None:
    """The agent copies the helper from isometric.md; the examples show that same code."""
    assert _block(SKILL / "isometric.md", "js") in _block(example, "html")


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda p: p.stem)
def test_each_examples_script_parses_without_eval(example: Path) -> None:
    """The page's policy allows inline script only, so no eval or new Function."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    script = _block(example, "html").split("<script>", 1)[1].split("</script>", 1)[0]
    assert "eval(" not in script
    assert "new Function" not in script
    subprocess.run(
        [
            node,
            "-e",
            "new (require('vm').Script)(require('fs').readFileSync(0, 'utf8'))",
        ],
        input=script,
        text=True,
        check=True,
        timeout=20,
    )
