"""Add created_by_id column to documents table for document ownership tracking

Revision ID: 86
Revises: 85
Create Date: 2026-02-02

Changes:
1. Add created_by_id column (UUID, nullable, foreign key to user.id)
2. Create index on created_by_id for performance
3. Backfill existing documents with search space owner's user_id
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "86"
down_revision: str | None = "85"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add created_by_id column to documents and backfill with search space owner."""

    # 1. Add created_by_id column (nullable for backward compatibility)
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'documents' AND column_name = 'created_by_id'
            ) THEN
                ALTER TABLE documents
                ADD COLUMN created_by_id UUID;
            END IF;
        END$$;
        """
    )

    # 2. Create index on created_by_id for efficient queries
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_documents_created_by_id
        ON documents (created_by_id);
        """
    )

    # 3. Add foreign key constraint with ON DELETE SET NULL
    # First check if constraint already exists
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE constraint_name = 'fk_documents_created_by_id'
                AND table_name = 'documents'
            ) THEN
                ALTER TABLE documents
                ADD CONSTRAINT fk_documents_created_by_id
                FOREIGN KEY (created_by_id) REFERENCES "user"(id)
                ON DELETE SET NULL;
            END IF;
        END$$;
        """
    )

    # 4. Backfill existing documents with search space owner's user_id
    # This ensures all existing documents are associated with the search space owner
    op.execute(
        """
        UPDATE documents
        SET created_by_id = searchspaces.user_id
        FROM searchspaces
        WHERE documents.search_space_id = searchspaces.id
        AND documents.created_by_id IS NULL;
        """
    )


def downgrade() -> None:
    """Remove created_by_id column from documents."""

    # Drop foreign key constraint
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE constraint_name = 'fk_documents_created_by_id'
                AND table_name = 'documents'
            ) THEN
                ALTER TABLE documents
                DROP CONSTRAINT fk_documents_created_by_id;
            END IF;
        END$$;
        """
    )

    # Drop index
    op.execute(
        """
        DROP INDEX IF EXISTS ix_documents_created_by_id;
        """
    )

    # Drop column
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'documents' AND column_name = 'created_by_id'
            ) THEN
                ALTER TABLE documents
                DROP COLUMN created_by_id;
            END IF;
        END$$;
        """
    )

