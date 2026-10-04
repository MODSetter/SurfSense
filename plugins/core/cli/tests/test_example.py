import re
import shutil

import pytest

from surfsense_plugin_cli.repository import PLUGINS

pytestmark = pytest.mark.app


@pytest.fixture
def example(tmp_path):
    """A copy of plugins/example as git holds it, without what an invoke left there."""
    copy = tmp_path / "plugins" / "example"
    left_by_invoke = shutil.ignore_patterns("dev-data", "site-packages", "__pycache__")
    shutil.copytree(PLUGINS / "example", copy, ignore=left_by_invoke)
    return copy


def test_the_example_counts_words_into_numbered_notes(cli, example, real_app) -> None:
    """The plugin the guide points at, dependency and all, as an author first runs it.

    Installs tabulate from PyPI: the one test that needs the network.
    """
    workspace = real_app.new_workspace()
    arguments = (
        "invoke",
        str(example),
        "count-words",
        "--input",
        "text=a b a",
        "--input",
        "top=2",
        "--api-url",
        real_app.url,
        "--workspace",
        str(workspace),
    )

    first, second = cli(*arguments), cli(*arguments)

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    notes = real_app.call("GET", f"/workspaces/{workspace}/documents")
    assert sorted(note["title"] for note in notes) == ["Word count #1", "Word count #2"]
    [latest] = [note for note in notes if note["title"] == "Word count #2"]
    read = real_app.call("GET", f"/workspaces/{workspace}/documents/{latest['id']}")
    content = read["content"]
    assert content.startswith("a b a\n")
    assert re.search(r"^\| a\s+\|\s+2 \|$", content, re.MULTILINE)
    assert re.search(r"^\| b\s+\|\s+1 \|$", content, re.MULTILINE)
