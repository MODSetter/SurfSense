"""Contract-3 producer: every exported document gets a path of its own."""

from __future__ import annotations

import json
import os
import zipfile
from types import SimpleNamespace

import pytest

from app.db import Document, DocumentType
from app.services.export_service import build_account_export_zip

pytestmark = pytest.mark.unit


class _Rows:
    def __init__(self, rows: list):
        self._rows = rows

    def scalars(self):
        return self

    def unique(self):
        return self

    def all(self):
        return self._rows


class _Session:
    """Answers the exporter's queries in order: workspaces, folders, document
    batches, then chat threads."""

    def __init__(self, workspace, documents: list[Document]):
        self._responses = [[workspace], [], documents, [], []]

    async def execute(self, _stmt):
        return _Rows(self._responses.pop(0))


def _note(doc_id: int, title: str) -> Document:
    return Document(
        id=doc_id,
        title=title,
        document_type=DocumentType.NOTE,
        source_markdown=f"Body of document {doc_id}",
    )


async def test_suffixed_name_does_not_overwrite_a_title_that_already_has_it():
    workspace = SimpleNamespace(id=7, name="Research", created_at=None)
    documents = [_note(1, "Notes"), _note(2, "Notes_2"), _note(3, "Notes")]

    result = await build_account_export_zip(_Session(workspace, documents), "user")
    try:
        with zipfile.ZipFile(result.zip_path) as archive:
            manifest = json.loads(archive.read("manifest.json"))
            listed = manifest["workspaces"][0]["documents"]
            paths = [doc["path"] for doc in listed]
            assert len(set(paths)) == len(paths)
            for doc in listed:
                assert (
                    f"Body of document {doc['id']}"
                    in archive.read(doc["path"]).decode()
                )
    finally:
        os.unlink(result.zip_path)
