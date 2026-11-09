"""The workspace's documents, as a plugin adds, lists and edits them.

Each verb calls one route in the run's workspace and returns a typed result,
never the app's raw reply.
"""

import builtins
from dataclasses import dataclass
from typing import TypedDict, cast

from surfsense_plugin_sdk.app.client import (
    get_from_workspace,
    patch_in_workspace,
    post_to_workspace,
)
from surfsense_plugin_sdk.app.context import run_id
from surfsense_plugin_sdk.run.current_run import current_run


@dataclass(frozen=True)
class Document:
    """A document as a plugin needs it: enough to find it again."""

    id: int
    title: str


class _Row(TypedDict):
    """The fields of the app's document reply that the SDK reads."""

    id: int
    title: str


# The most the documents route returns at once.
PAGE_SIZE = 200


def add(title: str, content: str) -> Document:
    """Adds a note to the workspace, marked with the plugin and run that wrote it."""
    run = current_run()
    reply = post_to_workspace(
        "/documents",
        {
            "title": title,
            "content": content,
            "document_metadata": {
                "plugin_id": run.manifest["id"],
                "plugin_version": run.manifest.get("version"),
                "action": run.action,
                "run_id": run_id(),
            },
        },
    )
    return _document_from(reply)


def list() -> builtins.list[Document]:
    """Every document in the workspace, newest first."""
    found: builtins.list[Document] = []
    while True:
        page = cast(
            builtins.list[_Row],
            get_from_workspace(f"/documents?limit={PAGE_SIZE}&offset={len(found)}"),
        )
        found += [_document_from(row) for row in page]
        if len(page) < PAGE_SIZE:
            return found


def update(
    document_id: int, *, title: str | None = None, content: str | None = None
) -> Document:
    """Only a note's content can change; a file's comes from the file."""
    changes = {"title": title, "content": content}
    reply = patch_in_workspace(
        f"/documents/{document_id}",
        {field: value for field, value in changes.items() if value is not None},
    )
    return _document_from(reply)


def _document_from(reply: object) -> Document:
    """Keeps what a plugin uses from the app's reply."""
    row = cast(_Row, reply)
    return Document(id=row["id"], title=row["title"])
