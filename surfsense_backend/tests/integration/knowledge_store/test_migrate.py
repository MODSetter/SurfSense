"""Phase 5 seeder: seed commit + byte parity (real git engine + real Redis lock)."""

from __future__ import annotations

import pytest

from app.config import config as app_config
from app.knowledge_store import KnowledgeStore
from app.knowledge_store.identities import MIGRATION_IDENTITY
from app.knowledge_store.migrate import seed_workspace

pytestmark = pytest.mark.integration

FILES = {
    "notes/roadmap.md": "# Roadmap",
    "notes/okrs.md": "# OKRs",
    "welcome.md": "# Welcome",
}


@pytest.fixture
def knowledge_root(tmp_path, monkeypatch):
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ROOT", str(tmp_path))
    return tmp_path


async def test_seed_records_one_revision_and_passes_parity(
    knowledge_root, workspace_id
):
    report = await seed_workspace(workspace_id, FILES)

    assert report.ok
    assert report.seeded_revision is not None
    assert report.files == 3
    assert report.missing == report.extra == report.mismatched == []

    store = KnowledgeStore.for_workspace(workspace_id)
    revisions = await store.list_revisions()
    assert [r.id for r in revisions] == [report.seeded_revision]
    assert revisions[0].author == MIGRATION_IDENTITY
    assert await store.read_as_of(report.seeded_revision, "notes/okrs.md") == b"# OKRs"


async def test_reseeding_unchanged_content_is_a_noop(knowledge_root, workspace_id):
    first = await seed_workspace(workspace_id, FILES)
    second = await seed_workspace(workspace_id, FILES)

    assert second.ok
    assert second.seeded_revision is None
    revisions = await KnowledgeStore.for_workspace(workspace_id).list_revisions()
    assert [r.id for r in revisions] == [first.seeded_revision]


async def test_dry_run_builds_nothing_and_reports_all_missing(
    knowledge_root, workspace_id
):
    report = await seed_workspace(workspace_id, FILES, dry_run=True)

    assert not report.ok
    assert report.seeded_revision is None
    assert sorted(report.missing) == sorted(FILES)
    assert not (knowledge_root / str(workspace_id)).exists()


async def test_dry_run_against_a_seeded_store_passes_parity(
    knowledge_root, workspace_id
):
    await seed_workspace(workspace_id, FILES)

    report = await seed_workspace(workspace_id, FILES, dry_run=True)

    assert report.ok
    assert report.seeded_revision is None


async def test_reseeding_after_drift_converges(knowledge_root, workspace_id):
    """Seed-then-flip-later: Postgres kept changing; a catch-up re-seed heals
    everything, including documents deleted since the first seed."""
    await seed_workspace(workspace_id, FILES)

    drifted = dict(FILES)
    drifted.pop("welcome.md")  # deleted in Postgres since the first seed
    drifted["notes/okrs.md"] = "# OKRs v2"  # edited
    drifted["notes/new.md"] = "# New"  # added
    report = await seed_workspace(workspace_id, drifted)

    assert report.ok
    assert report.seeded_revision is not None
    store = KnowledgeStore.for_workspace(workspace_id)
    paths = {t.path for t in await store.list_paths(report.seeded_revision)}
    assert "welcome.md" not in paths
    assert (
        await store.read_as_of(report.seeded_revision, "notes/okrs.md") == b"# OKRs v2"
    )


async def test_parity_names_missing_extra_and_mismatched_paths(
    knowledge_root, workspace_id
):
    await seed_workspace(workspace_id, FILES)

    drifted = dict(FILES)
    drifted.pop("welcome.md")  # repo now has an extra path
    drifted["notes/okrs.md"] = "# OKRs v2"  # repo content differs
    drifted["notes/new.md"] = "# New"  # repo misses this path
    report = await seed_workspace(workspace_id, drifted, dry_run=True)

    assert not report.ok
    assert report.missing == ["notes/new.md"]
    assert report.extra == ["welcome.md"]
    assert report.mismatched == ["notes/okrs.md"]


async def test_a_leftover_keep_in_a_populated_folder_is_not_drift(
    knowledge_root, workspace_id
):
    """A folder created empty keeps its .keep after a document lands beside it.
    The seeder derives no marker for a populated folder, so without this the
    drift check would alarm the folder forever and draw a futile repair."""
    store = KnowledgeStore.for_workspace(workspace_id)
    async with store.transaction(message="seed", author=MIGRATION_IDENTITY) as tx:
        tx.write("notes/plan.md", b"# Plan")
        tx.write("notes/.keep", b"")  # the empty-folder marker left behind

    report = await seed_workspace(
        workspace_id, {"notes/plan.md": "# Plan"}, dry_run=True
    )

    assert report.ok
    assert report.extra == []


async def test_expired_write_lock_lands_in_the_report(
    knowledge_root, workspace_id, monkeypatch
):
    """A real TTL expiry — the seed write outlives the Redis lock — is reported,
    never swallowed or raised past the fleet loop. The commit itself still
    landed (parity is clean), so ``error`` is the only trace of the lost hold."""
    import time

    import app.knowledge_store.locks as write_lock
    from app.knowledge_store.engines.git import GitContentEngine

    real_record = GitContentEngine.record

    def slow_record(self, **kwargs):
        time.sleep(0.3)  # outlive the shrunken TTL below
        return real_record(self, **kwargs)

    monkeypatch.setattr(write_lock, "LOCK_TTL_SECONDS", 0.1)
    monkeypatch.setattr(GitContentEngine, "record", slow_record)
    report = await seed_workspace(workspace_id, FILES)

    assert not report.ok
    assert "expired mid-block" in report.error
    assert report.seeded_revision is None
    assert report.missing == report.extra == report.mismatched == []


async def test_any_seed_failure_is_contained_in_the_report(
    knowledge_root, workspace_id, monkeypatch
):
    """seed_workspace never raises: a crash anywhere (here the parity read)
    becomes ``error``, so one broken workspace can't abort a fleet run."""

    def explode(self, revision):
        raise OSError("disk gone")

    monkeypatch.setattr(KnowledgeStore, "list_paths", explode)
    report = await seed_workspace(workspace_id, FILES)

    assert not report.ok
    assert report.error == "OSError: disk gone"
    assert report.files == len(FILES)
