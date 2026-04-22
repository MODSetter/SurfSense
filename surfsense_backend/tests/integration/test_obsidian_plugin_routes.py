"""Integration tests for the Obsidian plugin HTTP wire contract.

Three concerns:

1. The /connect upsert really collapses concurrent first-time connects to
   exactly one row. This locks the partial unique index from migration 129
   to its purpose.
2. The fingerprint dedup path: a second device connecting with a fresh
   ``vault_id`` but the same ``vault_fingerprint`` adopts the existing
   connector instead of creating a duplicate.
3. The end-to-end response shapes returned by /connect /sync /rename
   /notes /manifest /stats match the schemas the plugin's TypeScript
   decoders expect. Each renamed field is a contract change, and a smoke
   pass like this is the cheapest way to catch a future drift before it
   ships.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import (
    SearchSourceConnector,
    SearchSourceConnectorType,
    SearchSpace,
    User,
)
from app.routes.obsidian_plugin_routes import (
    obsidian_connect,
    obsidian_delete_notes,
    obsidian_manifest,
    obsidian_rename,
    obsidian_stats,
    obsidian_sync,
)
from app.schemas.obsidian_plugin import (
    ConnectRequest,
    DeleteAck,
    DeleteBatchRequest,
    HeadingRef,
    ManifestResponse,
    NotePayload,
    RenameAck,
    RenameBatchRequest,
    RenameItem,
    StatsResponse,
    SyncAck,
    SyncBatchRequest,
)

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_note_payload(vault_id: str, path: str, content_hash: str) -> NotePayload:
    """Minimal NotePayload that the schema accepts; the indexer is mocked
    out so the values don't have to round-trip through the real pipeline."""
    now = datetime.now(UTC)
    return NotePayload(
        vault_id=vault_id,
        path=path,
        name=path.rsplit("/", 1)[-1].rsplit(".", 1)[0],
        extension="md",
        content="# Test\n\nbody",
        headings=[HeadingRef(heading="Test", level=1)],
        content_hash=content_hash,
        mtime=now,
        ctime=now,
    )


@pytest_asyncio.fixture
async def race_user_and_space(async_engine):
    """User + SearchSpace committed via the live engine so the two
    concurrent /connect sessions in the race test can both see them.

    We can't use the savepoint-trapped ``db_session`` fixture here
    because the concurrent sessions need to see committed rows.
    """
    user_id = uuid.uuid4()
    async with AsyncSession(async_engine) as setup:
        user = User(
            id=user_id,
            email=f"obsidian-race-{uuid.uuid4()}@surfsense.test",
            hashed_password="x",
            is_active=True,
            is_superuser=False,
            is_verified=True,
        )
        space = SearchSpace(name="Race Space", user_id=user_id)
        setup.add_all([user, space])
        await setup.commit()
        await setup.refresh(space)
        space_id = space.id

    yield user_id, space_id

    async with AsyncSession(async_engine) as cleanup:
        # Order matters: connectors -> documents -> space -> user. The
        # connectors test creates documents, so we wipe them too. The
        # CASCADE on user_id catches anything we missed.
        await cleanup.execute(
            text("DELETE FROM search_source_connectors WHERE user_id = :uid"),
            {"uid": user_id},
        )
        await cleanup.execute(
            text("DELETE FROM searchspaces WHERE id = :id"),
            {"id": space_id},
        )
        await cleanup.execute(
            text('DELETE FROM "user" WHERE id = :uid'),
            {"uid": user_id},
        )
        await cleanup.commit()


# ---------------------------------------------------------------------------
# /connect race + index enforcement
# ---------------------------------------------------------------------------


class TestConnectRace:
    async def test_concurrent_first_connects_collapse_to_one_row(
        self, async_engine, race_user_and_space
    ):
        """Two simultaneous /connect calls for the same vault should
        produce exactly one row, not two. Same vault_id + same
        fingerprint funnels through both partial unique indexes; the
        loser falls back to the survivor row via the IntegrityError
        branch in obsidian_connect."""
        user_id, space_id = race_user_and_space
        vault_id = str(uuid.uuid4())
        fingerprint = "fp-" + uuid.uuid4().hex

        async def _call(name_suffix: str) -> None:
            async with AsyncSession(async_engine) as s:
                fresh_user = await s.get(User, user_id)
                payload = ConnectRequest(
                    vault_id=vault_id,
                    vault_name=f"My Vault {name_suffix}",
                    search_space_id=space_id,
                    vault_fingerprint=fingerprint,
                )
                await obsidian_connect(payload, user=fresh_user, session=s)

        results = await asyncio.gather(_call("a"), _call("b"), return_exceptions=True)
        for r in results:
            assert not isinstance(r, Exception), f"Connect raised: {r!r}"

        async with AsyncSession(async_engine) as verify:
            count = (
                await verify.execute(
                    select(func.count(SearchSourceConnector.id)).where(
                        SearchSourceConnector.user_id == user_id,
                    )
                )
            ).scalar_one()
            assert count == 1

    async def test_partial_unique_index_blocks_raw_duplicate(
        self, async_engine, race_user_and_space
    ):
        """Raw INSERTs that bypass the route must still be blocked by
        the partial unique indexes from migration 129."""
        user_id, space_id = race_user_and_space
        vault_id = str(uuid.uuid4())

        async with AsyncSession(async_engine) as s:
            s.add(
                SearchSourceConnector(
                    name="Obsidian - First",
                    connector_type=SearchSourceConnectorType.OBSIDIAN_CONNECTOR,
                    is_indexable=False,
                    config={
                        "vault_id": vault_id,
                        "vault_name": "First",
                        "source": "plugin",
                        "vault_fingerprint": "fp-1",
                    },
                    user_id=user_id,
                    search_space_id=space_id,
                )
            )
            await s.commit()

        with pytest.raises(IntegrityError):
            async with AsyncSession(async_engine) as s:
                s.add(
                    SearchSourceConnector(
                        name="Obsidian - Second",
                        connector_type=SearchSourceConnectorType.OBSIDIAN_CONNECTOR,
                        is_indexable=False,
                        config={
                            "vault_id": vault_id,
                            "vault_name": "Second",
                            "source": "plugin",
                            "vault_fingerprint": "fp-2",
                        },
                        user_id=user_id,
                        search_space_id=space_id,
                    )
                )
                await s.commit()

    async def test_fingerprint_blocks_raw_cross_device_duplicate(
        self, async_engine, race_user_and_space
    ):
        """Two connectors for the same user with different vault_ids but
        the same fingerprint cannot coexist."""
        user_id, space_id = race_user_and_space
        fingerprint = "fp-" + uuid.uuid4().hex

        async with AsyncSession(async_engine) as s:
            s.add(
                SearchSourceConnector(
                    name="Obsidian - Desktop",
                    connector_type=SearchSourceConnectorType.OBSIDIAN_CONNECTOR,
                    is_indexable=False,
                    config={
                        "vault_id": str(uuid.uuid4()),
                        "vault_name": "Vault",
                        "source": "plugin",
                        "vault_fingerprint": fingerprint,
                    },
                    user_id=user_id,
                    search_space_id=space_id,
                )
            )
            await s.commit()

        with pytest.raises(IntegrityError):
            async with AsyncSession(async_engine) as s:
                s.add(
                    SearchSourceConnector(
                        name="Obsidian - Mobile",
                        connector_type=SearchSourceConnectorType.OBSIDIAN_CONNECTOR,
                        is_indexable=False,
                        config={
                            "vault_id": str(uuid.uuid4()),
                            "vault_name": "Vault",
                            "source": "plugin",
                            "vault_fingerprint": fingerprint,
                        },
                        user_id=user_id,
                        search_space_id=space_id,
                    )
                )
                await s.commit()

    async def test_second_device_adopts_existing_connector_via_fingerprint(
        self, async_engine, race_user_and_space
    ):
        """Device A connects with vault_id=A. Device B then connects with
        a fresh vault_id=B but the same fingerprint. The route must
        return A's identity (not create a B row), proving cross-device
        dedup happens transparently to the plugin."""
        user_id, space_id = race_user_and_space
        vault_id_a = str(uuid.uuid4())
        vault_id_b = str(uuid.uuid4())
        fingerprint = "fp-" + uuid.uuid4().hex

        async with AsyncSession(async_engine) as s:
            fresh_user = await s.get(User, user_id)
            resp_a = await obsidian_connect(
                ConnectRequest(
                    vault_id=vault_id_a,
                    vault_name="Shared Vault",
                    search_space_id=space_id,
                    vault_fingerprint=fingerprint,
                ),
                user=fresh_user,
                session=s,
            )

        async with AsyncSession(async_engine) as s:
            fresh_user = await s.get(User, user_id)
            resp_b = await obsidian_connect(
                ConnectRequest(
                    vault_id=vault_id_b,
                    vault_name="Shared Vault",
                    search_space_id=space_id,
                    vault_fingerprint=fingerprint,
                ),
                user=fresh_user,
                session=s,
            )

        assert resp_b.vault_id == vault_id_a
        assert resp_b.connector_id == resp_a.connector_id

        async with AsyncSession(async_engine) as verify:
            count = (
                await verify.execute(
                    select(func.count(SearchSourceConnector.id)).where(
                        SearchSourceConnector.user_id == user_id,
                    )
                )
            ).scalar_one()
            assert count == 1


# ---------------------------------------------------------------------------
# Combined wire-shape smoke test
# ---------------------------------------------------------------------------


class TestWireContractSmoke:
    """Walks /connect -> /sync -> /rename -> /notes -> /manifest -> /stats
    sequentially and asserts each response matches the new schema. With
    `response_model=` on every route, FastAPI is already validating the
    shape on real traffic; this test mainly guards against accidental
    field renames the way the TypeScript decoder would catch them."""

    async def test_full_flow_returns_typed_payloads(
        self, db_session: AsyncSession, db_user: User, db_search_space: SearchSpace
    ):
        vault_id = str(uuid.uuid4())

        # 1. /connect
        connect_resp = await obsidian_connect(
            ConnectRequest(
                vault_id=vault_id,
                vault_name="Smoke Vault",
                search_space_id=db_search_space.id,
                vault_fingerprint="fp-" + uuid.uuid4().hex,
            ),
            user=db_user,
            session=db_session,
        )
        assert connect_resp.connector_id > 0
        assert connect_resp.vault_id == vault_id
        assert "sync" in connect_resp.capabilities

        # 2. /sync — stub the indexer so the call doesn't drag the LLM /
        # embedding pipeline in. We're testing the wire contract, not the
        # indexer itself.
        fake_doc = type("FakeDoc", (), {"id": 12345})()
        with patch(
            "app.routes.obsidian_plugin_routes.upsert_note",
            new=AsyncMock(return_value=fake_doc),
        ):
            sync_resp = await obsidian_sync(
                SyncBatchRequest(
                    vault_id=vault_id,
                    notes=[
                        _make_note_payload(vault_id, "ok.md", "hash-ok"),
                        _make_note_payload(vault_id, "fail.md", "hash-fail"),
                    ],
                ),
                user=db_user,
                session=db_session,
            )

        assert isinstance(sync_resp, SyncAck)
        assert sync_resp.vault_id == vault_id
        assert sync_resp.indexed == 2
        assert sync_resp.failed == 0
        assert len(sync_resp.items) == 2
        assert all(it.status == "ok" for it in sync_resp.items)
        # The TypeScript decoder filters on items[].status === "error" and
        # extracts .path, so confirm both fields are present and named.
        assert {it.path for it in sync_resp.items} == {"ok.md", "fail.md"}

        # 2b. Re-run /sync but force the indexer to raise on one note so
        # the per-item failure decoder gets exercised end-to-end.
        async def _selective_upsert(session, *, connector, payload, user_id):
            if payload.path == "fail.md":
                raise RuntimeError("simulated indexing failure")
            return fake_doc

        with patch(
            "app.routes.obsidian_plugin_routes.upsert_note",
            new=AsyncMock(side_effect=_selective_upsert),
        ):
            sync_resp = await obsidian_sync(
                SyncBatchRequest(
                    vault_id=vault_id,
                    notes=[
                        _make_note_payload(vault_id, "ok.md", "h1"),
                        _make_note_payload(vault_id, "fail.md", "h2"),
                    ],
                ),
                user=db_user,
                session=db_session,
            )
        assert sync_resp.indexed == 1
        assert sync_resp.failed == 1
        statuses = {it.path: it.status for it in sync_resp.items}
        assert statuses == {"ok.md": "ok", "fail.md": "error"}

        # 3. /rename — patch rename_note so we don't need a real Document.
        async def _rename(*args, **kwargs) -> object:
            if kwargs.get("old_path") == "missing.md":
                return None
            return fake_doc

        with patch(
            "app.routes.obsidian_plugin_routes.rename_note",
            new=AsyncMock(side_effect=_rename),
        ):
            rename_resp = await obsidian_rename(
                RenameBatchRequest(
                    vault_id=vault_id,
                    renames=[
                        RenameItem(old_path="a.md", new_path="b.md"),
                        RenameItem(old_path="missing.md", new_path="x.md"),
                    ],
                ),
                user=db_user,
                session=db_session,
            )
        assert isinstance(rename_resp, RenameAck)
        assert rename_resp.renamed == 1
        assert rename_resp.missing == 1
        assert {it.status for it in rename_resp.items} == {"ok", "missing"}
        # snake_case fields are deliberate — the plugin decoder maps them
        # to camelCase explicitly.
        assert all(it.old_path and it.new_path for it in rename_resp.items)

        # 4. /notes DELETE
        async def _delete(*args, **kwargs) -> bool:
            return kwargs.get("path") != "ghost.md"

        with patch(
            "app.routes.obsidian_plugin_routes.delete_note",
            new=AsyncMock(side_effect=_delete),
        ):
            delete_resp = await obsidian_delete_notes(
                DeleteBatchRequest(vault_id=vault_id, paths=["b.md", "ghost.md"]),
                user=db_user,
                session=db_session,
            )
        assert isinstance(delete_resp, DeleteAck)
        assert delete_resp.deleted == 1
        assert delete_resp.missing == 1
        assert {it.path: it.status for it in delete_resp.items} == {
            "b.md": "ok",
            "ghost.md": "missing",
        }

        # 5. /manifest — empty (no real Documents were created because
        # upsert_note was mocked) but the response shape is what we care
        # about.
        manifest_resp = await obsidian_manifest(
            vault_id=vault_id, user=db_user, session=db_session
        )
        assert isinstance(manifest_resp, ManifestResponse)
        assert manifest_resp.vault_id == vault_id
        assert manifest_resp.items == {}

        # 6. /stats — same; row count is 0 because upsert_note was mocked.
        stats_resp = await obsidian_stats(
            vault_id=vault_id, user=db_user, session=db_session
        )
        assert isinstance(stats_resp, StatsResponse)
        assert stats_resp.vault_id == vault_id
        assert stats_resp.files_synced == 0
        assert stats_resp.last_sync_at is None
