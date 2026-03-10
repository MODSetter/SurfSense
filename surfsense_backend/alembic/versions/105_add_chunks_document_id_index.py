"""105_add_chunks_document_id_index

Revision ID: 105
Revises: 104
Create Date: 2026-03-09

Adds a B-tree index on chunks.document_id to speed up chunk lookups
during hybrid search (both retrievers fetch chunks by document_id
after RRF ranking selects the top documents).
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "105"
down_revision: str | None = "104"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_indexes
                WHERE tablename = 'chunks' AND indexname = 'ix_chunks_document_id'
            ) THEN
                CREATE INDEX ix_chunks_document_id ON chunks(document_id);
            END IF;
        END$$;
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_chunks_document_id")
