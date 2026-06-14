"""add chunks.position for explicit document order

Incremental re-indexing keeps unchanged chunk rows, so auto-increment ids no
longer reflect document order. Backfill preserves the historical id ordering.

Revision ID: 164
Revises: 163
"""

from collections.abc import Sequence

from alembic import op

revision: str = "164"
down_revision: str | None = "163"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE chunks ADD COLUMN IF NOT EXISTS position INTEGER NOT NULL DEFAULT 0;"
    )

    # Backfill: document order so far has been the insertion order (id).
    op.execute(
        """
        UPDATE chunks
        SET position = numbered.rn
        FROM (
            SELECT id,
                   ROW_NUMBER() OVER (PARTITION BY document_id ORDER BY id) - 1 AS rn
            FROM chunks
        ) AS numbered
        WHERE chunks.id = numbered.id;
        """
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_chunks_position ON chunks(position);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_chunks_document_id_position "
        "ON chunks(document_id, position);"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_chunks_document_id_position;")
    op.execute("DROP INDEX IF EXISTS ix_chunks_position;")
    op.execute("ALTER TABLE chunks DROP COLUMN IF EXISTS position;")
