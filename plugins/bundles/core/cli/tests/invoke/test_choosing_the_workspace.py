import pytest

pytestmark = pytest.mark.app


def test_with_one_workspace_invoke_writes_to_it(
    cli, plugin_that_adds_a_note, fresh_app
) -> None:
    """A first install has one workspace, and nothing to choose between."""
    [only] = fresh_app.call("GET", "/workspaces")

    finished = cli(
        "invoke",
        str(plugin_that_adds_a_note.folder),
        "echo",
        "--input",
        "text=hi",
        "--api-url",
        fresh_app.url,
    )

    assert finished.returncode == 0, finished.stderr
    [note] = fresh_app.call("GET", f"/workspaces/{only['id']}/documents")
    assert str(note["id"]) == finished.stdout.strip()


def test_with_several_workspaces_invoke_lists_them_and_runs_nothing(
    cli, plugin_that_adds_a_note, real_app
) -> None:
    """Writing into a workspace the author did not pick would surprise them."""
    real_app.new_workspace()
    workspaces = real_app.call("GET", "/workspaces")

    finished = cli(
        "invoke",
        str(plugin_that_adds_a_note.folder),
        "echo",
        "--input",
        "text=hi",
        "--api-url",
        real_app.url,
    )

    assert finished.returncode == 1
    assert "--workspace" in finished.stderr
    for workspace in workspaces:
        assert f"{workspace['id']}  {workspace['name']}" in finished.stderr
    assert finished.stdout == ""
