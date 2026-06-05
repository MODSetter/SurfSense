"""Tests for the @-mention resolver.

These tests pin down the contract that ``mention_resolver`` is the
single seam between ``MentionedDocumentInfo`` chips (frontend) and the
canonical ``/documents/...`` virtual paths (agent). The streaming task,
priority middleware, and persistence layer all consume the resolver's
output — keeping the tests focused on substitute-in-text + the
returned id partition keeps the seam stable across refactors.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.chat.multi_agent_chat.shared import mention_resolver
from app.agents.chat.multi_agent_chat.shared.mention_resolver import (
    ResolvedMention,
    ResolvedMentionSet,
    resolve_mentions,
    substitute_in_text,
)
from app.agents.chat.multi_agent_chat.shared.path_resolver import (
    DOCUMENTS_ROOT,
    PathIndex,
)
from app.schemas.new_chat import MentionedDocumentInfo

pytestmark = pytest.mark.unit


class TestSubstituteInText:
    """``substitute_in_text`` is a pure string transform and is exercised
    on every cloud-mode turn, so it has to be both fast and behaviour-
    identical to the frontend's ``parseMentionSegments`` (longest-token
    first, single forward pass)."""

    def test_returns_text_unchanged_when_no_tokens(self):
        assert substitute_in_text("hello @foo", []) == "hello @foo"

    def test_returns_text_unchanged_when_empty(self):
        assert substitute_in_text("", [("@x", "/documents/x.xml")]) == ""

    def test_replaces_single_token_with_backtick_path(self):
        out = substitute_in_text(
            "see @notes please",
            [("@notes", "/documents/notes.xml")],
        )
        assert out == "see `/documents/notes.xml` please"

    def test_longest_token_wins_over_prefix(self):
        # ``@Project Roadmap`` must NOT be partially matched by ``@Project``.
        # Mirrors the FE's parseMentionSegments contract.
        token_to_path = [
            ("@Project Roadmap", "/documents/Roadmap.xml"),
            ("@Project", "/documents/Project.xml"),
        ]
        out = substitute_in_text("about @Project Roadmap today", token_to_path)
        assert out == "about `/documents/Roadmap.xml` today"

    def test_handles_repeated_mentions(self):
        out = substitute_in_text(
            "@A and @A again @B",
            [
                ("@A", "/documents/a.xml"),
                ("@B", "/documents/b.xml"),
            ],
        )
        assert (
            out == "`/documents/a.xml` and `/documents/a.xml` again `/documents/b.xml`"
        )

    def test_does_not_match_inside_word(self):
        # Substitution is positional — there's no word-boundary semantics.
        # ``@Pro`` inside ``foo@Project`` still matches; this is the same
        # behaviour as parseMentionSegments. The test pins it so a
        # future "fix" doesn't accidentally diverge between FE/BE.
        out = substitute_in_text("foo@Pro", [("@Pro", "/documents/p.xml")])
        assert out == "foo`/documents/p.xml`"

    def test_idempotent_after_substitution(self):
        # The output starts with a backtick, not ``@``, so re-running
        # the substitution leaves it alone.
        once = substitute_in_text("@A", [("@A", "/documents/a.xml")])
        twice = substitute_in_text(once, [("@A", "/documents/a.xml")])
        assert once == twice


class TestResolveMentions:
    """``resolve_mentions`` resolves chip ids → virtual paths and emits
    a ``ResolvedMentionSet`` whose id partitions feed
    ``KnowledgePriorityMiddleware``."""

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_mentions(self):
        session = MagicMock()
        session.execute = AsyncMock()
        result = await resolve_mentions(
            session,
            search_space_id=1,
            mentioned_documents=None,
        )
        assert isinstance(result, ResolvedMentionSet)
        assert result.mentions == []
        assert result.token_to_path == []
        assert result.mentioned_document_ids == []
        assert result.mentioned_folder_ids == []
        # No DB roundtrips when there's nothing to resolve.
        session.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_resolves_doc_chip_to_virtual_path(self, monkeypatch):
        chip = MentionedDocumentInfo(
            id=42,
            title="Notes",
            document_type="EXTENSION",
            kind="doc",
        )
        doc_row = SimpleNamespace(id=42, title="Notes", folder_id=None)

        async def fake_build_index(_session, _ssid):
            return PathIndex()

        monkeypatch.setattr(mention_resolver, "build_path_index", fake_build_index)

        scalars = MagicMock()
        scalars.all.return_value = [doc_row]
        result = MagicMock()
        result.scalars.return_value = scalars
        session = MagicMock()
        session.execute = AsyncMock(return_value=result)

        out = await resolve_mentions(
            session,
            search_space_id=5,
            mentioned_documents=[chip],
        )
        assert len(out.mentions) == 1
        mention = out.mentions[0]
        assert mention.kind == "doc"
        assert mention.id == 42
        assert mention.virtual_path == f"{DOCUMENTS_ROOT}/Notes.xml"
        assert out.mentioned_document_ids == [42]
        assert out.mentioned_folder_ids == []
        assert ("@Notes", f"{DOCUMENTS_ROOT}/Notes.xml") in out.token_to_path

    @pytest.mark.asyncio
    async def test_resolves_folder_chip_with_trailing_slash(self, monkeypatch):
        chip = MentionedDocumentInfo(
            id=9,
            title="Reports",
            document_type="FOLDER",
            kind="folder",
        )
        folder_row = SimpleNamespace(id=9, name="Reports")

        async def fake_build_index(_session, _ssid):
            return PathIndex(folder_paths={9: f"{DOCUMENTS_ROOT}/Reports"})

        monkeypatch.setattr(mention_resolver, "build_path_index", fake_build_index)

        scalars = MagicMock()
        scalars.all.return_value = [folder_row]
        result = MagicMock()
        result.scalars.return_value = scalars
        session = MagicMock()
        session.execute = AsyncMock(return_value=result)

        out = await resolve_mentions(
            session,
            search_space_id=3,
            mentioned_documents=[chip],
        )
        assert len(out.mentions) == 1
        mention = out.mentions[0]
        assert mention.kind == "folder"
        assert mention.id == 9
        assert mention.virtual_path == f"{DOCUMENTS_ROOT}/Reports/"
        assert out.mentioned_document_ids == []
        assert out.mentioned_folder_ids == [9]

    @pytest.mark.asyncio
    async def test_drops_chip_when_doc_is_missing(self, monkeypatch):
        chip = MentionedDocumentInfo(
            id=99, title="ghost", document_type="EXTENSION", kind="doc"
        )

        async def fake_build_index(_session, _ssid):
            return PathIndex()

        monkeypatch.setattr(mention_resolver, "build_path_index", fake_build_index)

        scalars = MagicMock()
        scalars.all.return_value = []
        result = MagicMock()
        result.scalars.return_value = scalars
        session = MagicMock()
        session.execute = AsyncMock(return_value=result)

        out = await resolve_mentions(
            session,
            search_space_id=1,
            mentioned_documents=[chip],
        )
        assert out.mentions == []
        assert out.mentioned_document_ids == []
        assert out.token_to_path == []

    @pytest.mark.asyncio
    async def test_token_to_path_is_longest_first(self, monkeypatch):
        # Two chips whose titles are prefixes of each other — the
        # resolver MUST sort longest-first so substitution doesn't
        # break the ``@Project Roadmap`` vs ``@Project`` invariant.
        chip_short = MentionedDocumentInfo(
            id=1, title="A", document_type="EXTENSION", kind="doc"
        )
        chip_long = MentionedDocumentInfo(
            id=2, title="A long one", document_type="EXTENSION", kind="doc"
        )
        rows = [
            SimpleNamespace(id=1, title="A", folder_id=None),
            SimpleNamespace(id=2, title="A long one", folder_id=None),
        ]

        async def fake_build_index(_session, _ssid):
            return PathIndex()

        monkeypatch.setattr(mention_resolver, "build_path_index", fake_build_index)

        scalars = MagicMock()
        scalars.all.return_value = rows
        result = MagicMock()
        result.scalars.return_value = scalars
        session = MagicMock()
        session.execute = AsyncMock(return_value=result)

        out = await resolve_mentions(
            session,
            search_space_id=1,
            mentioned_documents=[chip_short, chip_long],
        )
        tokens = [tok for tok, _ in out.token_to_path]
        assert tokens == sorted(tokens, key=len, reverse=True)

    @pytest.mark.asyncio
    async def test_legacy_id_arrays_resolve_without_chip_metadata(self, monkeypatch):
        # ``mentioned_document_ids`` (the legacy parallel array) must
        # still resolve when no chip metadata is available — covers
        # callers that haven't migrated to the discriminated chip list.
        doc_row = SimpleNamespace(id=7, title="Legacy", folder_id=None)

        async def fake_build_index(_session, _ssid):
            return PathIndex()

        monkeypatch.setattr(mention_resolver, "build_path_index", fake_build_index)

        scalars = MagicMock()
        scalars.all.return_value = [doc_row]
        result = MagicMock()
        result.scalars.return_value = scalars
        session = MagicMock()
        session.execute = AsyncMock(return_value=result)

        out = await resolve_mentions(
            session,
            search_space_id=2,
            mentioned_documents=None,
            mentioned_document_ids=[7],
        )
        assert out.mentioned_document_ids == [7]
        assert len(out.mentions) == 1
        assert out.mentions[0].title == "Legacy"


class TestResolvedMentionEquality:
    """Smoke check on the dataclass behaviour we rely on for asserting
    test outputs."""

    def test_equal_when_fields_equal(self):
        a = ResolvedMention(
            kind="doc", id=1, title="x", virtual_path="/documents/x.xml"
        )
        b = ResolvedMention(
            kind="doc", id=1, title="x", virtual_path="/documents/x.xml"
        )
        assert a == b
