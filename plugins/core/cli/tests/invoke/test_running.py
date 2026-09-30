import pytest

pytestmark = pytest.mark.app


def test_invoke_runs_the_action_once_against_the_app(
    cli, plugin_that_adds_a_note, real_app
) -> None:
    """The author's plugin writes into their SurfSense, as it will once installed."""
    workspace = real_app.new_workspace()

    finished = cli(
        "invoke",
        str(plugin_that_adds_a_note.folder),
        "echo",
        "--input",
        "text=hi",
        "--api-url",
        real_app.url,
        "--workspace",
        str(workspace),
    )

    assert finished.returncode == 0, finished.stderr
    note = real_app.call(
        "GET", f"/workspaces/{workspace}/documents/{finished.stdout.strip()}"
    )
    assert note["content"] == "hi"


def test_invoke_exits_with_the_plugins_own_code(cli, plugin, real_app) -> None:
    """A script or CI step can tell a failed run from a good one."""
    plugin.write(
        """
import sys

from surfsense_plugin_sdk import action


@action("echo")
def echo(text: str) -> None:
    sys.exit(3)
"""
    )

    finished = cli(
        "invoke",
        str(plugin.folder),
        "echo",
        "--input",
        "text=hi",
        "--api-url",
        real_app.url,
        "--workspace",
        str(real_app.new_workspace()),
    )

    assert finished.returncode == 3
