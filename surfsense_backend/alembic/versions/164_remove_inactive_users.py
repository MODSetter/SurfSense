"""remove users that never logged back in (last_login IS NULL)

Migration 103 added ``user.last_login``. Any user whose ``last_login`` is still
NULL has never authenticated since that column existed, i.e. they never logged
back in. This migration purges those users together with everything that hangs
off them: the search spaces they own, and (via ON DELETE CASCADE)
``searchspaces -> documents -> chunks`` plus all other user/space-scoped rows.

This runs BEFORE the chunks.position backfill (revision 165) on purpose: it
removes a large amount of dead chunk data first, so the expensive backfill has
far fewer rows to rewrite.

Work is done in committed batches (not one giant cascading DELETE) so that on a
large table it streams progress to the alembic console, keeps each transaction
small, bounds WAL/bloat growth, and is resumable if interrupted.

Revision ID: 164
Revises: 163
"""

import logging
import time
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "164"
down_revision: str | None = "163"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Documents removed per committed batch. Each document delete cascades to its
# chunks (via ix_chunks_document_id), so keep this modest to bound batch size.
DOC_BATCH = 1_000
# Users removed per committed batch. Each cascades to owned search spaces and
# the remaining space-/user-scoped rows.
USER_BATCH = 500
# Minimum seconds between progress log lines (keeps the console readable).
LOG_EVERY_SECONDS = 5.0

USER_SCRATCH = "_inactive_user_ids"
DOC_SCRATCH = "_inactive_doc_ids"

logger = logging.getLogger("alembic.runtime.migration")


def _fmt_duration(seconds: float) -> str:
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h{m:02d}m{s:02d}s"
    if m:
        return f"{m}m{s:02d}s"
    return f"{s}s"


def upgrade() -> None:
    bind = op.get_bind()

    # Run the heavy work outside the migration's single transaction so each
    # batch can commit on its own.
    with op.get_context().autocommit_block():
        # Materialize the target user ids once. Rebuilt from scratch on every
        # run, so a re-run after an interruption simply picks up whoever still
        # has NULL last_login -> the migration is idempotent and resumable.
        op.execute(f"DROP TABLE IF EXISTS {USER_SCRATCH};")
        op.execute(
            f'CREATE UNLOGGED TABLE {USER_SCRATCH} AS '
            'SELECT id FROM "user" WHERE last_login IS NULL;'
        )
        op.execute(f"ALTER TABLE {USER_SCRATCH} ADD PRIMARY KEY (id);")

        total_users = (
            bind.execute(sa.text(f"SELECT count(*) FROM {USER_SCRATCH}")).scalar() or 0
        )
        if total_users == 0:
            logger.info("no users with NULL last_login; nothing to remove")
            op.execute(f"DROP TABLE IF EXISTS {USER_SCRATCH};")
            return

        logger.info(
            "found %s users with NULL last_login (never logged back in); "
            "removing them and all data in search spaces they own",
            f"{total_users:,}",
        )

        # Documents living in search spaces owned by those users. Deleting these
        # explicitly (in batches) is what bounds the otherwise-unbounded
        # chunks cascade.
        op.execute(f"DROP TABLE IF EXISTS {DOC_SCRATCH};")
        op.execute(
            f"""
            CREATE UNLOGGED TABLE {DOC_SCRATCH} AS
            SELECT d.id
            FROM documents d
            JOIN searchspaces s ON s.id = d.search_space_id
            WHERE s.user_id IN (SELECT id FROM {USER_SCRATCH});
            """
        )
        op.execute(f"ALTER TABLE {DOC_SCRATCH} ADD PRIMARY KEY (id);")
        total_docs = (
            bind.execute(sa.text(f"SELECT count(*) FROM {DOC_SCRATCH}")).scalar() or 0
        )

        # Phase 1: delete documents (cascades chunks, document_versions,
        # document_files) in committed batches.
        logger.info(
            "phase 1/2: deleting %s documents (cascades their chunks) "
            "in batches of %s...",
            f"{total_docs:,}",
            f"{DOC_BATCH:,}",
        )
        _batched_delete(
            bind,
            scratch=DOC_SCRATCH,
            target_table="documents",
            target_col="id",
            batch_size=DOC_BATCH,
            total=total_docs,
            label="documents",
        )
        op.execute(f"DROP TABLE IF EXISTS {DOC_SCRATCH};")

        # Phase 2: delete the users themselves. This cascades the now-empty
        # search spaces plus all remaining user-/space-scoped rows.
        logger.info(
            "phase 2/2: deleting %s users (cascades search spaces and "
            "remaining data) in batches of %s...",
            f"{total_users:,}",
            f"{USER_BATCH:,}",
        )
        _batched_delete(
            bind,
            scratch=USER_SCRATCH,
            target_table='"user"',
            target_col="id",
            batch_size=USER_BATCH,
            total=total_users,
            label="users",
        )
        op.execute(f"DROP TABLE IF EXISTS {USER_SCRATCH};")

        logger.info("migration 164 finished")


def _batched_delete(
    bind: sa.engine.Connection,
    *,
    scratch: str,
    target_table: str,
    target_col: str,
    batch_size: int,
    total: int,
    label: str,
) -> None:
    """Pop ids from ``scratch`` and delete the matching rows, one committed
    batch at a time, logging progress. Atomic per batch: the row delete and the
    scratch pop happen in a single statement, so an interrupted run leaves the
    scratch table in sync with what has actually been deleted."""
    started = time.monotonic()
    last_log = 0.0
    done = 0

    stmt = sa.text(
        f"""
        WITH batch AS (
            SELECT id FROM {scratch} LIMIT :n
        ), deleted AS (
            DELETE FROM {target_table}
            WHERE {target_col} IN (SELECT id FROM batch)
        ), popped AS (
            DELETE FROM {scratch}
            WHERE id IN (SELECT id FROM batch)
            RETURNING id
        )
        SELECT count(*) FROM popped
        """
    )

    while True:
        popped = bind.execute(stmt, {"n": batch_size}).scalar() or 0
        if popped == 0:
            break
        done += popped

        now = time.monotonic()
        if now - last_log >= LOG_EVERY_SECONDS or done >= total:
            elapsed = now - started
            pct = (100.0 * done / total) if total else 100.0
            eta = (elapsed / pct * (100.0 - pct)) if pct > 0 else 0.0
            logger.info(
                "%s deleted: %.1f%% (%s/%s) elapsed %s eta %s",
                label,
                pct,
                f"{done:,}",
                f"{total:,}",
                _fmt_duration(elapsed),
                _fmt_duration(eta),
            )
            last_log = now

    logger.info(
        "deleted %s %s in %s",
        f"{done:,}",
        label,
        _fmt_duration(time.monotonic() - started),
    )


def downgrade() -> None:
    # Irreversible: deleted users and their cascaded data cannot be restored.
    # No-op so the downgrade chain can still pass through this revision.
    logger.warning(
        "migration 164 (remove_inactive_users) is irreversible; "
        "downgrade is a no-op (deleted users/data are not restored)"
    )
