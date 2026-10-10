import socket

import pytest


def _invoke(cli, plugin, *extra: str, environment=None):
    """Invoke the note plugin's action, adding whatever the test is about."""
    return cli(
        "invoke",
        str(plugin.folder),
        "echo",
        "--input",
        "text=hi",
        *extra,
        environment=environment,
    )


@pytest.mark.app
@pytest.mark.parametrize("folder", [".surfsense-dev", ".surfsense"])
def test_invoke_finds_the_app_by_the_file_it_writes(
    cli, plugin_that_adds_a_note, real_app, home, folder: str
) -> None:
    """A development app and a packaged one each announce where they answer."""
    (home / folder).mkdir()
    (home / folder / "api-url").write_text(real_app.url)
    workspace = real_app.new_workspace()

    finished = _invoke(cli, plugin_that_adds_a_note, "--workspace", str(workspace))

    assert finished.returncode == 0, finished.stderr
    assert real_app.call("GET", f"/workspaces/{workspace}/documents")


@pytest.mark.app
def test_invoke_finds_the_app_named_in_the_environment(
    cli, plugin_that_adds_a_note, real_app
) -> None:
    """The same variable the app's runner sets, so a script can point at an app."""
    workspace = real_app.new_workspace()

    finished = _invoke(
        cli,
        plugin_that_adds_a_note,
        "--workspace",
        str(workspace),
        environment={"SURFSENSE_PLUGIN_API_URL": real_app.url},
    )

    assert finished.returncode == 0, finished.stderr
    assert real_app.call("GET", f"/workspaces/{workspace}/documents")


@pytest.mark.unit
def test_with_no_app_running_invoke_says_how_to_reach_one(
    cli, plugin_that_adds_a_note
) -> None:
    """The fix is to start SurfSense or name it, not to read a connection error."""
    finished = _invoke(cli, plugin_that_adds_a_note)

    assert finished.returncode == 1
    assert "SurfSense is not running" in finished.stderr
    assert "--api-url" in finished.stderr
    assert finished.stdout == ""


@pytest.mark.unit
def test_an_app_that_no_longer_answers_is_not_running(
    cli, plugin_that_adds_a_note, home
) -> None:
    """A file left behind by an app that crashed points nowhere."""
    with socket.socket() as unused:
        unused.bind(("127.0.0.1", 0))
        closed_port = unused.getsockname()[1]
    (home / ".surfsense-dev").mkdir()
    (home / ".surfsense-dev" / "api-url").write_text(f"http://127.0.0.1:{closed_port}")

    finished = _invoke(cli, plugin_that_adds_a_note)

    assert finished.returncode == 1
    assert "SurfSense is not running" in finished.stderr
    assert finished.stdout == ""
