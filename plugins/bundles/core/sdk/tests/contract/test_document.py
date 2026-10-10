import pytest

pytestmark = pytest.mark.contract


@pytest.mark.covers("document.add")
def test_add_leaves_the_note_and_its_document_metadata_in_the_app(
    plugin, real_app
) -> None:
    """The app keeps the note, and names the plugin, action and run that wrote it."""
    workspace = real_app.new_workspace()
    plugin.write(
        """
from surfsense_plugin_sdk import action, document


@action("echo")
def echo(text: str) -> None:
    print(document.add(title="Word count #1", content=text).id)
"""
    )

    finished = plugin.run(
        "echo", {"text": "a b a"}, context=real_app.context(workspace)
    )

    assert finished.returncode == 0, finished.stderr
    note = real_app.call(
        "GET", f"/workspaces/{workspace}/documents/{finished.stdout.strip()}"
    )
    assert note["document_type"] == "NOTE"
    assert (note["title"], note["content"]) == ("Word count #1", "a b a")
    assert note["document_metadata"] == {
        "plugin_id": "example",
        "plugin_version": None,
        "action": "echo",
        "run_id": 41,
    }


@pytest.mark.covers("document.list")
def test_list_returns_every_document_the_app_holds(plugin, real_app) -> None:
    """More than one of the app's pages, so a change to its page size shows here."""
    workspace = real_app.new_workspace()
    for number in range(201):
        real_app.call(
            "POST",
            f"/workspaces/{workspace}/documents",
            {"title": f"Note {number}", "content": "x"},
        )
    plugin.write(
        """
from surfsense_plugin_sdk import action, document


@action("echo")
def echo(text: str) -> None:
    found = document.list()
    print(len(found), found[0].title, found[-1].title)
"""
    )

    finished = plugin.run("echo", {"text": "hi"}, context=real_app.context(workspace))

    assert finished.returncode == 0, finished.stderr
    assert finished.stdout == "201 Note 200 Note 0\n"


@pytest.mark.covers("document.update")
def test_update_changes_the_note_in_the_app(plugin, real_app) -> None:
    """What the verb returns is what the app now holds."""
    workspace = real_app.new_workspace()
    created = real_app.call(
        "POST",
        f"/workspaces/{workspace}/documents",
        {"title": "Draft", "content": "first"},
    )
    plugin.write(
        f"""
from surfsense_plugin_sdk import action, document


@action("echo")
def echo(text: str) -> None:
    updated = document.update({created["id"]}, title="Final", content=text)
    print(updated.id, updated.title)
"""
    )

    finished = plugin.run(
        "echo", {"text": "second"}, context=real_app.context(workspace)
    )

    assert finished.returncode == 0, finished.stderr
    assert finished.stdout == f"{created['id']} Final\n"
    note = real_app.call("GET", f"/workspaces/{workspace}/documents/{created['id']}")
    assert (note["title"], note["content"]) == ("Final", "second")


def test_a_refusal_carries_the_apps_own_reason(plugin, real_app) -> None:
    """The message an author reads is the one the real app writes."""
    workspace = real_app.new_workspace()
    plugin.write(
        """
from surfsense_plugin_sdk import action, document


@action("echo")
def echo(text: str) -> None:
    document.update(999999, title=text)
"""
    )

    finished = plugin.run("echo", {"text": "hi"}, context=real_app.context(workspace))

    assert finished.returncode == 1
    assert "AppRefused: document not found\n" in finished.stderr
