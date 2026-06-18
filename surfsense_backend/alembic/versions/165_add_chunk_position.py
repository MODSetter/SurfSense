"""add chunks.position for explicit document order

Incremental re-indexing keeps unchanged chunk rows, so auto-increment ids no
longer reflect document order. Backfill preserves the historical id ordering.

The backfill is done in committed batches (not one giant UPDATE) so that on a
large table it: streams progress to the alembic console, keeps each transaction
small, bounds WAL/bloat growth, and is resumable if interrupted.

Revision ID: 165
Revises: 164
"""

import logging
import time
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "165"
down_revision: str | None = "164"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Number of chunk ids processed per committed batch.
BATCH_SIZE = 100_000
# Minimum seconds between progress log lines (keeps the console readable).
LOG_EVERY_SECONDS = 5.0
SCRATCH_TABLE = "_chunk_position_backfill"

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


def _index_exists(bind: sa.engine.Connection, name: str) -> bool:
    return bool(
        bind.execute(
            sa.text(
                "SELECT EXISTS (SELECT 1 FROM pg_class "
                "WHERE relkind = 'i' AND relname = :n)"
            ),
            {"n": name},
        ).scalar()
    )


def upgrade() -> None:
    bind = op.get_bind()

    # Adding a NOT NULL column with a constant default is metadata-only on
    # PostgreSQL 11+, so this is fast even on very large tables.
    op.execute(
        "ALTER TABLE chunks ADD COLUMN IF NOT EXISTS position INTEGER NOT NULL DEFAULT 0;"
    )

    # Idempotent fast path: both indexes are created only after the backfill
    # has fully completed, so their presence is a reliable "already applied"
    # marker. This makes re-running the migration a cheap no-op.
    if _index_exists(bind, "ix_chunks_position") and _index_exists(
        bind, "ix_chunks_document_id_position"
    ):
        logger.info("migration 165 already applied; skipping backfill")
        return

    # Run the heavy work outside the migration's single transaction so each
    # batch can commit on its own.
    with op.get_context().autocommit_block():
        # reltuples is a planner estimate and is -1 on never-analyzed tables;
        # it is only used for the log line below, so treat <= 0 as "unknown".
        total_rows = (
            bind.execute(
                sa.text(
                    "SELECT reltuples::bigint FROM pg_class WHERE relname = 'chunks'"
                )
            ).scalar()
            or 0
        )
        total_rows_display = f"~{total_rows:,}" if total_rows > 0 else "an unknown number of"

        bounds = bind.execute(
            sa.text("SELECT min(id), max(id) FROM chunks")
        ).one()
        min_id, max_id = bounds[0], bounds[1]

        if min_id is None:
            logger.info("chunks table is empty; nothing to backfill")
        else:
            # Precompute per-document ordering once into an UNLOGGED scratch
            # table (low WAL). ROW_NUMBER must see each whole document, so it
            # cannot be computed per id-range slice.
            logger.info(
                "building position mapping for %s chunks (this is a single "
                "scan; the batched UPDATE below reports progress)...",
                total_rows_display,
            )
            op.execute(f"DROP TABLE IF EXISTS {SCRATCH_TABLE};")
            op.execute(
                f"""
                CREATE UNLOGGED TABLE {SCRATCH_TABLE} AS
                SELECT id,
                       (ROW_NUMBER() OVER (PARTITION BY document_id ORDER BY id) - 1)::int AS rn
                FROM chunks;
                """
            )
            op.execute(f"ALTER TABLE {SCRATCH_TABLE} ADD PRIMARY KEY (id);")

            id_span = max(max_id - min_id + 1, 1)
            started = time.monotonic()
            last_log = 0.0
            updated_total = 0

            lo = min_id
            while lo <= max_id:
                hi = lo + BATCH_SIZE  # exclusive upper bound
                result = bind.execute(
                    sa.text(
                        f"""
                        UPDATE chunks c
                        SET position = m.rn
                        FROM {SCRATCH_TABLE} m
                        WHERE c.id = m.id
                          AND c.id >= :lo
                          AND c.id < :hi
                          AND c.position IS DISTINCT FROM m.rn
                        """
                    ),
                    {"lo": lo, "hi": hi},
                )
                updated_total += result.rowcount or 0

                now = time.monotonic()
                processed_ids = min(hi, max_id + 1) - min_id
                pct = min(100.0, 100.0 * processed_ids / id_span)
                if now - last_log >= LOG_EVERY_SECONDS or hi > max_id:
                    elapsed = now - started
                    eta = (elapsed / pct * (100.0 - pct)) if pct > 0 else 0.0
                    logger.info(
                        "backfill position: %.1f%% (id<%s, %s rows rewritten) "
                        "elapsed %s eta %s",
                        pct,
                        f"{min(hi, max_id + 1):,}",
                        f"{updated_total:,}",
                        _fmt_duration(elapsed),
                        _fmt_duration(eta),
                    )
                    last_log = now

                lo = hi

            logger.info(
                "backfill complete: %s rows rewritten in %s",
                f"{updated_total:,}",
                _fmt_duration(time.monotonic() - started),
            )
            op.execute(f"DROP TABLE IF EXISTS {SCRATCH_TABLE};")

        logger.info("creating index ix_chunks_position...")
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_chunks_position ON chunks(position);"
        )
        logger.info("creating index ix_chunks_document_id_position...")
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_chunks_document_id_position "
            "ON chunks(document_id, position);"
        )
        logger.info("migration 165 finished")


def downgrade() -> None:
    op.execute(f"DROP TABLE IF EXISTS {SCRATCH_TABLE};")
    op.execute("DROP INDEX IF EXISTS ix_chunks_document_id_position;")
    op.execute("DROP INDEX IF EXISTS ix_chunks_position;")
    op.execute("ALTER TABLE chunks DROP COLUMN IF EXISTS position;")
