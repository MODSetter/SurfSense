import pytest

pytestmark = pytest.mark.unit


def _row(document_id: int, title: str) -> dict:
    """A document as the app's documents routes return it."""
    return {
        "id": document_id,
        "title": title,
        "document_type": "NOTE",
        "status": "pending",
        "error_message": None,
        "created_at": "2026-09-30T10:00:00",
        "updated_at": "2026-09-30T10:00:00",
    }


def test_add_writes_a_note_marked_with_where_it_came_from(plugin, app) -> None:
    """The note records the plugin, its version and the run, for the user to see."""
    app.answer(
        "POST", "/workspaces/7/documents", 201, _row(3, "Note hi") | {"content": "hi"}
    )
    plugin.write(
        """
from surfsense_plugin_sdk import action, document


@action("echo")
def echo(text: str) -> None:
    note = document.add(title=f"Note {text}", content=text)
    print(note.id, note.title)
"""
    )

    finished = plugin.run("echo", {"text": "hi"}, context=app.context())

    assert finished.returncode == 0, finished.stderr
    assert finished.stdout == "3 Note hi\n"
    [request] = app.received
    assert (request.method, request.path) == ("POST", "/workspaces/7/documents")
    assert request.body == {
        "title": "Note hi",
        "content": "hi",
        "metadata": {
            "plugin_id": "example",
            "plugin_version": None,
            "action": "echo",
            "run_id": 41,
        },
    }


def test_list_returns_every_document_however_many_pages_the_app_needs(
    plugin, app
) -> None:
    """The route pages for the screen; a plugin asking what exists wants all of it."""
    first = [_row(i, f"Doc {i}") for i in range(250, 50, -1)]
    rest = [_row(i, f"Doc {i}") for i in range(50, 0, -1)]
    app.answer("GET", "/workspaces/7/documents?limit=200&offset=0", 200, first)
    app.answer("GET", "/workspaces/7/documents?limit=200&offset=200", 200, rest)
    plugin.write(
        """
from surfsense_plugin_sdk import action, document


@action("echo")
def echo(text: str) -> None:
    found = document.list()
    print(len(found), found[0].title, found[-1].title)
"""
    )

    finished = plugin.run("echo", {"text": "hi"}, context=app.context())

    assert finished.returncode == 0, finished.stderr
    assert finished.stdout == "250 Doc 250 Doc 1\n"


def test_update_sends_only_what_changes_and_returns_the_document(plugin, app) -> None:
    """A title left out stays as it was."""
    app.answer("PATCH", "/workspaces/7/documents/3", 200, _row(3, "Note hi"))
    plugin.write(
        """
from surfsense_plugin_sdk import action, document


@action("echo")
def echo(text: str) -> None:
    updated = document.update(3, content=text)
    print(updated.id, updated.title)
"""
    )

    finished = plugin.run("echo", {"text": "hello"}, context=app.context())

    assert finished.returncode == 0, finished.stderr
    assert finished.stdout == "3 Note hi\n"
    [request] = app.received
    assert request.body == {"content": "hello"}


UPDATES_A_FILE = """
from surfsense_plugin_sdk import action, document


@action("echo")
def echo(text: str) -> None:
    document.update(3, title=text)
"""


@pytest.mark.parametrize(
    ("status", "detail", "reason"),
    [
        (409, "only a note's content is editable", "only a note's content is editable"),
        (
            403,
            {"code": "egress_disabled", "message": "egress is off"},
            "egress is off",
        ),
        (
            422,
            [
                {
                    "loc": ["body", "title"],
                    "msg": "String should have at least 1 character",
                }
            ],
            "title: String should have at least 1 character",
        ),
    ],
)
def test_a_refusal_fails_with_what_the_app_said(
    plugin, app, status: int, detail: object, reason: str
) -> None:
    """An author reads the app's reason, never a status code."""
    app.answer("PATCH", "/workspaces/7/documents/3", status, {"detail": detail})
    plugin.write(UPDATES_A_FILE)

    finished = plugin.run("echo", {"text": "hi"}, context=app.context())

    assert finished.returncode == 1
    assert f"AppRefused: {reason}\n" in finished.stderr
    assert str(status) not in finished.stderr.splitlines()[-1]


def test_a_verb_run_without_the_app_says_how_to_reach_one(plugin) -> None:
    """Outside the app, the fix is invoke and its flag, not a connection error."""
    plugin.write(UPDATES_A_FILE)

    finished = plugin.run("echo", {"text": "hi"})

    assert finished.returncode == 1
    assert "SURFSENSE_PLUGIN_API_URL is not set" in finished.stderr
    assert "--api-url" in finished.stderr


def test_the_app_is_reached_directly_when_the_user_has_a_proxy(plugin, app) -> None:
    """The user's proxy is for the plugin's egress; it cannot reach loopback."""
    app.answer("PATCH", "/workspaces/7/documents/3", 200, _row(3, "hi"))
    plugin.write(UPDATES_A_FILE)

    finished = plugin.run(
        "echo",
        {"text": "hi"},
        context=app.context(
            HTTP_PROXY="http://127.0.0.1:9", http_proxy="http://127.0.0.1:9"
        ),
    )

    assert finished.returncode == 0, finished.stderr
