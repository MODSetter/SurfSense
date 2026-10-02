import pytest

pytestmark = pytest.mark.app


def _invoke(cli, plugin, real_app, workspace: int):
    """Invoke the plugin's echo action in one workspace of the app."""
    return cli(
        "invoke",
        str(plugin.folder),
        "echo",
        "--input",
        "text=hi",
        "--api-url",
        real_app.url,
        "--workspace",
        str(workspace),
    )


def test_invoke_says_where_it_runs_and_that_it_finished(
    cli, plugin_that_adds_a_note, real_app
) -> None:
    """A run that worked is never silent: the author knows where to look."""
    workspace = real_app.new_workspace()

    finished = _invoke(cli, plugin_that_adds_a_note, real_app, workspace)

    assert finished.returncode == 0, finished.stderr
    assert f'Running echo of example in "CLI test" at {real_app.url}' in finished.stderr
    assert finished.stderr.rstrip().endswith("Done.")


def test_invoke_says_how_a_failed_run_ended(cli, plugin, real_app) -> None:
    """The exit code the app would record, after the plugin's own reason."""
    plugin.write(
        """
import sys

from surfsense_plugin_sdk import action


@action("echo")
def echo(text: str) -> None:
    sys.exit("the source is down")
"""
    )

    finished = _invoke(cli, plugin, real_app, real_app.new_workspace())

    assert finished.returncode == 1
    assert "the source is down" in finished.stderr
    assert finished.stderr.rstrip().endswith("Failed: exit 1.")


def test_a_workspace_the_app_does_not_have_is_refused_before_running(
    cli, plugin_that_adds_a_note, real_app
) -> None:
    """Named, with the workspaces there are, rather than failing inside the plugin."""
    finished = _invoke(cli, plugin_that_adds_a_note, real_app, 999999)

    assert finished.returncode == 1
    assert "SurfSense has no workspace 999999" in finished.stderr
    assert "CLI test" in finished.stderr
    assert finished.stdout == ""
