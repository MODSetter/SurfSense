"""add chunks.position for explicit document order

Incremental re-indexing keeps unchanged chunk rows, so auto-increment ids no
longer reflect document order. The ``position`` column makes that order
explicit and is written by the indexing pipeline for every new or re-indexed
document.

This migration intentionally does NOT backfill historical rows. On a large,
heavily-indexed table (notably a multi-hundred-GB HNSW embedding index) a bulk
UPDATE of every chunk becomes a non-HOT update that rewrites every secondary
index per row -- turning a one-off migration into a multi-day operation.
Instead, existing rows keep ``position = 0`` and therefore order by the
``Chunk.id`` tiebreaker (identical to the pre-feature behavior); new and
re-indexed documents get correct positions from application code, and any
document needing exact order can simply be re-indexed on demand.

Revision ID: 165
Revises: 164
"""

from collections.abc import Sequence

from alembic import op

revision: str = "165"
down_revision: str | None = "164"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Leftover UNLOGGED scratch table from earlier backfill attempts; dropped here
# so re-running this migration converges the schema regardless of past state.
SCRATCH_TABLE = "_chunk_position_backfill"


def upgrade() -> None:
    # Adding a NOT NULL column with a constant default is metadata-only on
    # PostgreSQL 11+, so this is fast even on very large tables. IF NOT EXISTS
    # makes it a no-op where the column already exists.
    op.execute(
        "ALTER TABLE chunks ADD COLUMN IF NOT EXISTS position INTEGER NOT NULL DEFAULT 0;"
    )

    # Clean up the scratch table left behind by the abandoned backfill approach.
    op.execute(f"DROP TABLE IF EXISTS {SCRATCH_TABLE};")


def downgrade() -> None:
    op.execute(f"DROP TABLE IF EXISTS {SCRATCH_TABLE};")
    op.execute("ALTER TABLE chunks DROP COLUMN IF EXISTS position;")
