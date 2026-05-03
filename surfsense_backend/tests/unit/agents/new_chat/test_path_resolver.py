"""Tests for canonical virtual-path resolver helpers."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.new_chat.path_resolver import (
    DOCUMENTS_ROOT,
    PathIndex,
    doc_to_virtual_path,
    parse_doc_id_suffix,
    parse_documents_path,
    safe_filename,
    safe_folder_segment,
    virtual_path_to_doc,
)

pytestmark = pytest.mark.unit


class TestSafeFilename:
    def test_appends_xml_extension(self):
        assert safe_filename("notes").endswith(".xml")

    def test_strips_invalid_chars(self):
        assert "/" not in safe_filename("a/b\\c.xml")

    def test_falls_back_when_empty(self):
        assert safe_filename("").endswith(".xml")
        assert safe_filename("///") == "untitled.xml" or safe_filename("///").endswith(
            ".xml"
        )


class TestSafeFolderSegment:
    def test_strips_path_separators(self):
        assert "/" not in safe_folder_segment("a/b")

    def test_falls_back(self):
        assert safe_folder_segment("") == "folder"


class TestParseDocIdSuffix:
    def test_parses_suffix(self):
        stem, doc_id = parse_doc_id_suffix("My Doc (42).xml")
        assert stem == "My Doc"
        assert doc_id == 42

    def test_no_suffix_returns_none(self):
        stem, doc_id = parse_doc_id_suffix("My Doc.xml")
        assert stem == "My Doc"
        assert doc_id is None

    def test_no_xml_extension(self):
        stem, doc_id = parse_doc_id_suffix("plain")
        assert stem == "plain"
        assert doc_id is None


class TestDocToVirtualPath:
    def test_root_when_no_folder(self):
        index = PathIndex()
        path = doc_to_virtual_path(doc_id=1, title="Hello", folder_id=None, index=index)
        assert path == f"{DOCUMENTS_ROOT}/Hello.xml"
        assert index.occupants[path] == 1

    def test_collision_picks_doc_id_suffix(self):
        index = PathIndex(occupants={f"{DOCUMENTS_ROOT}/Hello.xml": 7})
        path = doc_to_virtual_path(doc_id=8, title="Hello", folder_id=None, index=index)
        assert path == f"{DOCUMENTS_ROOT}/Hello (8).xml"
        assert index.occupants[path] == 8

    def test_uses_folder_path_when_known(self):
        index = PathIndex(folder_paths={5: f"{DOCUMENTS_ROOT}/notes"})
        path = doc_to_virtual_path(doc_id=2, title="A", folder_id=5, index=index)
        assert path == f"{DOCUMENTS_ROOT}/notes/A.xml"


class TestParseDocumentsPath:
    def test_extracts_folder_parts_and_title(self):
        parts, title = parse_documents_path(f"{DOCUMENTS_ROOT}/foo/bar/baz.xml")
        assert parts == ["foo", "bar"]
        assert title == "baz"

    def test_strips_doc_id_suffix(self):
        parts, title = parse_documents_path(f"{DOCUMENTS_ROOT}/foo/My Doc (12).xml")
        assert parts == ["foo"]
        assert title == "My Doc"

    def test_non_documents_returns_empty(self):
        assert parse_documents_path("/other/x.xml") == ([], "")


def _result_from_scalars(rows: list):
    """Build a fake SQLAlchemy ``Result`` whose ``.scalars().all()`` and
    ``.scalars().first()`` yield ``rows``."""
    scalars = MagicMock()
    scalars.all.return_value = list(rows)
    scalars.first.return_value = rows[0] if rows else None
    result = MagicMock()
    result.scalars.return_value = scalars
    result.scalar_one_or_none.return_value = None
    result.first.return_value = None
    return result


def _result_from_one(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


class TestVirtualPathToDoc:
    """Lookup must round-trip through ``safe_filename``'s lossy encoding.

    The workspace tree displays ``safe_filename(title)`` as the basename, so
    when the agent passes that basename back to a tool (move/edit/read) the
    resolver must find the original document even though characters like
    ``:`` were replaced with ``_``.
    """

    @pytest.mark.asyncio
    async def test_falls_back_to_safe_filename_match_when_title_lossy(self):
        # A Google Calendar-style title that contains a colon — safe_filename
        # rewrites the colon to ``_``, so the literal title-equality lookup
        # would miss this row.
        original_title = "Calendar: Happy birthday!"
        encoded_basename = safe_filename(original_title)
        assert encoded_basename == "Calendar_ Happy birthday!.xml"

        target_doc = SimpleNamespace(id=42, title=original_title, folder_id=None)

        session = MagicMock()
        # Each ``await session.execute(...)`` returns a fresh canned result.
        # Order matches the resolver's lookup steps:
        #   1) unique_identifier_hash → no match
        #   2) literal title match → no match (lossy encoding)
        #   3) folder scan → returns the row whose title encodes to basename
        session.execute = AsyncMock(
            side_effect=[
                _result_from_one(None),
                _result_from_scalars([]),
                _result_from_scalars([target_doc]),
            ]
        )

        document = await virtual_path_to_doc(
            session,
            search_space_id=5,
            virtual_path=f"{DOCUMENTS_ROOT}/{encoded_basename}",
        )
        assert document is target_doc

    @pytest.mark.asyncio
    async def test_returns_none_when_no_doc_matches_safe_filename(self):
        session = MagicMock()
        session.execute = AsyncMock(
            side_effect=[
                _result_from_one(None),
                _result_from_scalars([]),
                _result_from_scalars(
                    [SimpleNamespace(id=1, title="Something else", folder_id=None)]
                ),
            ]
        )

        document = await virtual_path_to_doc(
            session,
            search_space_id=5,
            virtual_path=f"{DOCUMENTS_ROOT}/Calendar_ Happy birthday!.xml",
        )
        assert document is None

    @pytest.mark.asyncio
    async def test_literal_title_match_short_circuits_fallback(self):
        # When the literal title query hits, the folder-scan fallback must
        # NOT run (saves a query and avoids picking the wrong doc when two
        # rows share a lossy encoding).
        target_doc = SimpleNamespace(id=7, title="Plain Note", folder_id=None)

        session = MagicMock()
        session.execute = AsyncMock(
            side_effect=[
                _result_from_one(None),
                _result_from_scalars([target_doc]),
            ]
        )

        document = await virtual_path_to_doc(
            session,
            search_space_id=5,
            virtual_path=f"{DOCUMENTS_ROOT}/Plain Note.xml",
        )
        assert document is target_doc
        assert session.execute.await_count == 2
