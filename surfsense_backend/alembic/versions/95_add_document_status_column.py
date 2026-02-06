"""Add status column to documents table for per-document processing status

Revision ID: 95
Revises: 94
Create Date: 2026-02-05

Changes:
1. Add status column (JSONB) to documents table
2. Default value is {"state": "ready"} for backward compatibility
3. Existing documents are set to ready status
4. Index created for efficient status filtering
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "95"
down_revision: str | None = "94"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add status column to documents with default ready state."""

    # 1. Add status column with default value for new rows
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'documents' AND column_name = 'status'
            ) THEN
                ALTER TABLE documents
                ADD COLUMN status JSONB NOT NULL DEFAULT '{"state": "ready"}'::jsonb;
            END IF;
        END$$;
        """
    )

    # 2. Create index on status for efficient filtering by state
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_documents_status
        ON documents ((status->>'state'));
        """
    )


def downgrade() -> None:
    """Remove status column from documents."""

    # Drop index
    op.execute(
        """
        DROP INDEX IF EXISTS ix_documents_status;
        """
    )

    # Drop column
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'documents' AND column_name = 'status'
            ) THEN
                ALTER TABLE documents
                DROP COLUMN status;
            END IF;
        END$$;
        """
    )
