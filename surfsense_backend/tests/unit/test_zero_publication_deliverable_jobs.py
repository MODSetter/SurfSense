from pathlib import Path

from app import zero_publication


def test_deliverable_jobs_publish_only_public_lifecycle_columns(monkeypatch) -> None:
    actual_columns = set(zero_publication.DELIVERABLE_JOB_COLS) | {
        "_0_version",
        "request",
        "checkpoint",
        "celery_task_id",
        "internal_error",
        "heartbeat_at",
        "attempt_count",
    }
    monkeypatch.setattr(
        zero_publication,
        "_table_columns",
        lambda _conn, table: actual_columns if table == "deliverable_jobs" else set(),
    )

    entry = zero_publication._format_table_entry(object(), "deliverable_jobs")

    assert entry is not None
    assert '"_0_version"' in entry
    for column in (
        "request",
        "checkpoint",
        "celery_task_id",
        "internal_error",
        "heartbeat_at",
        "attempt_count",
        "cancel_requested_at",
        "claimed_at",
        "finished_at",
        "created_by_id",
        "tool_call_id",
    ):
        assert f'"{column}"' not in entry


def test_migration_188_reconciles_canonical_publication() -> None:
    migration = (
        Path(__file__).resolve().parents[2]
        / "alembic"
        / "versions"
        / "188_publish_deliverable_jobs_to_zero.py"
    ).read_text()

    assert 'revision: str = "188"' in migration
    assert 'down_revision: str | None = "187"' in migration
    assert "apply_publication(op.get_bind())" in migration
    assert "Historical publication shapes are immutable" in migration
