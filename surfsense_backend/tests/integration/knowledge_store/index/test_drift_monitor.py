"""The always-on parity check: real documents, real repos, real comparison.

This is what replaces reading migration reports by hand once workspaces are
flipped, so its verdict has to be trustworthy on its own — a check that says
``ok`` while git and Postgres disagree is worse than no check at all.
"""

from __future__ import annotations

import uuid
from dataclasses import replace

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

import app.tasks.celery_tasks.knowledge_store.drift_monitor_task as monitor
from app.config import config as app_config
from app.db import Document, DocumentStatus, DocumentType, Workspace
from app.knowledge_store.migrate import migrate_workspace

pytestmark = pytest.mark.integration


@pytest.fixture
def knowledge_root(tmp_path, monkeypatch):
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ENABLED", True)
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ROOT", str(tmp_path))
    return tmp_path


@pytest.fixture
def session_on_test_connection(db_session, monkeypatch):
    """The monitor opens its own sessions; point them at the test transaction.

    Patched on ``app.db`` rather than the task module because the monitor
    imports the maker at call time, per workspace.
    """
    import app.db as db

    maker = async_sessionmaker(
        bind=db_session.bind,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    monkeypatch.setattr(db, "async_session_maker", maker)


@pytest.fixture(autouse=True)
def repairs_enqueued(monkeypatch):
    """Record repairs instead of handing them to a broker that is not running.

    Autouse because ``.delay`` is the one outbound call in this module: a test
    that drifts without the seam in place would reach for a real broker.
    """
    calls: list[int] = []

    monkeypatch.setattr(
        monitor.reindex_knowledge_store,
        "delay",
        lambda workspace_id: calls.append(workspace_id),
    )
    return calls


@pytest.fixture
def drift_metrics(monkeypatch):
    """Record what the monitor reports, in place of an OTel exporter."""
    recorded: list[tuple[int, str]] = []

    monkeypatch.setattr(
        monitor.metrics,
        "record_knowledge_store_drift_check",
        lambda *, workspace_id, status: recorded.append((workspace_id, status)),
    )
    return recorded


@pytest.fixture
def drift_spans(monkeypatch):
    """Capture per-workspace drift spans, in place of an OTel exporter.

    Mirrors ``drift_metrics``: the span carries the drift *magnitude* the
    status-only metric cannot, so an alert can open a trace that already says
    how far git and Postgres are apart instead of sending someone to the logs.
    """
    import contextlib

    recorded: list[dict[str, object]] = []

    def fake_drift_check_span(**kwargs: object):
        recorded.append(kwargs)
        return contextlib.nullcontext()

    monkeypatch.setattr(monitor.otel, "drift_check_span", fake_drift_check_span)
    return recorded


async def make_workspace(session, user_id, *, flipped: bool) -> Workspace:
    space = Workspace(name="Watched", user_id=user_id, knowledge_store_enabled=flipped)
    session.add(space)
    await session.flush()
    return space


async def add_document(session, workspace, user_id, *, status=None) -> Document:
    document = Document(
        title="Note",
        document_type=DocumentType.NOTE,
        document_metadata={},
        content="# Note",
        content_hash=f"hash-{uuid.uuid4().hex}",
        unique_identifier_hash=f"unique-{uuid.uuid4().hex}",
        source_markdown="# Note\n\nBody.",
        workspace_id=workspace.id,
        created_by_id=user_id,
        status=status or DocumentStatus.ready(),
    )
    session.add(document)
    await session.flush()
    return document


async def test_a_seeded_workspace_reports_ok(
    db_session, db_user, knowledge_root, session_on_test_connection, drift_metrics
):
    space = await make_workspace(db_session, db_user.id, flipped=True)
    await add_document(db_session, space, db_user.id)
    await migrate_workspace(db_session, space.id)

    assert await monitor._check_flipped_workspaces() == {"ok": 1}
    assert drift_metrics == [(space.id, "ok")]


async def test_a_document_missing_from_the_store_reports_drift(
    db_session, db_user, knowledge_root, session_on_test_connection, drift_metrics
):
    """Postgres has content git never received — the exact case to alarm on."""
    space = await make_workspace(db_session, db_user.id, flipped=True)
    await add_document(db_session, space, db_user.id)
    await migrate_workspace(db_session, space.id)
    await add_document(db_session, space, db_user.id)

    assert await monitor._check_flipped_workspaces() == {"drift": 1}
    assert drift_metrics == [(space.id, "drift")]


async def test_the_drift_span_carries_the_magnitude(
    db_session,
    db_user,
    knowledge_root,
    session_on_test_connection,
    drift_metrics,
    drift_spans,
    repairs_enqueued,
):
    """The status-only metric says a workspace drifted; the span says by how much.

    One document Postgres holds and git never received is exactly one ``missing``
    path — the number that turns a red alert into a starting point.
    """
    space = await make_workspace(db_session, db_user.id, flipped=True)
    await add_document(db_session, space, db_user.id)
    await migrate_workspace(db_session, space.id)
    await add_document(db_session, space, db_user.id)

    assert await monitor._check_flipped_workspaces() == {"drift": 1}
    assert drift_spans == [
        {
            "workspace_id": space.id,
            "status": "drift",
            "missing": 1,
            "extra": 0,
            "mismatched": 0,
        }
    ]


async def test_a_row_never_placed_in_git_is_not_drift_until_it_is_ready(
    db_session,
    db_user,
    knowledge_root,
    session_on_test_connection,
    drift_metrics,
    repairs_enqueued,
):
    """A body that never earned a git file — still pending, or failed before it
    was recorded — is not content the store is missing; it is content the store
    was never asked to hold. Only a ready row is canonical. Counting an unready
    one alarms every run, and the repair (reindex, git→Postgres) cannot make a
    file out of a row, so the alarm and its no-op rebuild would recur forever.
    """
    space = await make_workspace(db_session, db_user.id, flipped=True)
    await add_document(db_session, space, db_user.id)
    await migrate_workspace(db_session, space.id)
    await add_document(db_session, space, db_user.id, status=DocumentStatus.pending())
    await add_document(
        db_session, space, db_user.id, status=DocumentStatus.failed("boom")
    )

    assert await monitor._check_flipped_workspaces() == {"ok": 1}
    assert repairs_enqueued == []


async def test_an_unflipped_workspace_is_not_checked(
    db_session, db_user, knowledge_root, session_on_test_connection, drift_metrics
):
    """Postgres is still its write model, so disagreeing with git is expected."""
    space = await make_workspace(db_session, db_user.id, flipped=False)
    await add_document(db_session, space, db_user.id)

    assert await monitor._check_flipped_workspaces() == {}
    assert drift_metrics == []


async def test_a_failed_check_is_reported_and_the_sweep_continues(
    db_session,
    db_user,
    knowledge_root,
    session_on_test_connection,
    drift_metrics,
    monkeypatch,
):
    """A workspace the check cannot read is its own status, not a lost run.

    The fresh session per workspace exists so one failure cannot poison the
    rest; a silent stop here would leave every later workspace unchecked while
    the task still looks healthy.
    """
    broken = await make_workspace(db_session, db_user.id, flipped=True)
    healthy = await make_workspace(db_session, db_user.id, flipped=True)
    await add_document(db_session, healthy, db_user.id)
    await migrate_workspace(db_session, healthy.id)

    real = monitor.migrate_workspace

    async def fail_on_broken(session, workspace_id, **kwargs):
        report = await real(session, workspace_id, **kwargs)
        if workspace_id == broken.id:
            return replace(report, error="repo unreadable")
        return report

    monkeypatch.setattr(monitor, "migrate_workspace", fail_on_broken)

    assert await monitor._check_flipped_workspaces() == {"error": 1, "ok": 1}
    assert (healthy.id, "ok") in drift_metrics


# ── Repair ──────────────────────────────────────────────────────────────────


async def test_drift_enqueues_a_whole_tree_converge(
    db_session,
    db_user,
    knowledge_root,
    session_on_test_connection,
    drift_metrics,
    repairs_enqueued,
):
    """The hourly sweep cannot see this drift, so the alarm has to close it.

    Both sides of the sweep's comparison are git revisions, which leaves
    Postgres-side disagreement to this check alone; if it only alarmed, repair
    would depend on someone reading the alert.
    """
    space = await make_workspace(db_session, db_user.id, flipped=True)
    await add_document(db_session, space, db_user.id)
    await migrate_workspace(db_session, space.id)
    await add_document(db_session, space, db_user.id)

    assert await monitor._check_flipped_workspaces() == {"drift": 1}
    assert repairs_enqueued == [space.id]


async def test_a_workspace_in_parity_is_not_repaired(
    db_session,
    db_user,
    knowledge_root,
    session_on_test_connection,
    drift_metrics,
    repairs_enqueued,
):
    """A daily whole-tree converge per healthy workspace is the cost of a bug here."""
    space = await make_workspace(db_session, db_user.id, flipped=True)
    await add_document(db_session, space, db_user.id)
    await migrate_workspace(db_session, space.id)

    assert await monitor._check_flipped_workspaces() == {"ok": 1}
    assert repairs_enqueued == []


async def test_a_failed_check_alarms_without_repairing(
    db_session,
    db_user,
    knowledge_root,
    session_on_test_connection,
    drift_metrics,
    repairs_enqueued,
    monkeypatch,
):
    """A store the check could not read will not be fixed by indexing it harder.

    Repairing on ``error`` would also mean repairing on a verdict nobody
    computed: the parity fields of a failed report describe nothing.
    """
    space = await make_workspace(db_session, db_user.id, flipped=True)
    await add_document(db_session, space, db_user.id)

    real = monitor.migrate_workspace

    async def fail(session, workspace_id, **kwargs):
        return replace(await real(session, workspace_id, **kwargs), error="unreadable")

    monkeypatch.setattr(monitor, "migrate_workspace", fail)

    assert await monitor._check_flipped_workspaces() == {"error": 1}
    assert repairs_enqueued == []


async def test_the_cap_bounds_repairs_not_checks(
    db_session,
    db_user,
    knowledge_root,
    session_on_test_connection,
    drift_metrics,
    repairs_enqueued,
    monkeypatch,
):
    """Fleet-wide drift is a systemic fault; fanning out rebuilds compounds it.

    Every workspace is still checked and still alarms — only the repair is
    capped, so the signal stays complete while the work stays bounded.
    """
    monkeypatch.setattr(monitor, "REPAIR_ENQUEUE_CAP", 1)
    for _ in range(2):
        space = await make_workspace(db_session, db_user.id, flipped=True)
        await add_document(db_session, space, db_user.id)
        await migrate_workspace(db_session, space.id)
        await add_document(db_session, space, db_user.id)

    assert await monitor._check_flipped_workspaces() == {"drift": 2}
    assert len(repairs_enqueued) == 1
