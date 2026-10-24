"""Knowledge-base export: every exported document gets a path of its own."""

from __future__ import annotations

import os
import zipfile

import pytest

from app.db import Document, DocumentType
from app.services.export_service import build_export_zip

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
    """Answers the exporter's queries in order: folders, one document batch, then
    the empty batch that ends its loop."""

    def __init__(self, documents: list[Document]):
        self._responses = [[], documents, []]

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
    documents = [_note(1, "Notes"), _note(2, "Notes_2"), _note(3, "Notes")]

    result = await build_export_zip(_Session(documents), workspace_id=7)
    try:
        with zipfile.ZipFile(result.zip_path) as archive:
            files = {name: archive.read(name).decode() for name in archive.namelist()}
        holders = [
            [
                name
                for name, body in files.items()
                if f"Body of document {doc.id}" in body
            ]
            for doc in documents
        ]
        assert all(len(found) == 1 for found in holders), holders
        assert len({found[0] for found in holders}) == len(documents)
    finally:
        os.unlink(result.zip_path)
