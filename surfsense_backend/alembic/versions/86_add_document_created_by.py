"""Add created_by_id column to documents table for document ownership tracking

Revision ID: 86
Revises: 85
Create Date: 2026-02-02

Changes:
1. Add created_by_id column (UUID, nullable, foreign key to user.id)
2. Create index on created_by_id for performance
3. Backfill existing documents with search space owner's user_id (with progress indicator)
"""

import sys
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "86"
down_revision: str | None = "85"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Batch size for backfill operation
BATCH_SIZE = 5000


def upgrade() -> None:
    """Add created_by_id column to documents and backfill with search space owner."""

    # 1. Add created_by_id column (nullable for backward compatibility)
    print("Step 1/4: Adding created_by_id column...")
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
    print("  Done: created_by_id column added.")

    # 2. Create index on created_by_id for efficient queries
    print("Step 2/4: Creating index on created_by_id...")
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_documents_created_by_id
        ON documents (created_by_id);
        """
    )
    print("  Done: Index created.")

    # 3. Add foreign key constraint with ON DELETE SET NULL
    # First check if constraint already exists
    print("Step 3/4: Adding foreign key constraint...")
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
    print("  Done: Foreign key constraint added.")

    # 4. Backfill existing documents with search space owner's user_id
    # Process in batches with progress indicator
    print("Step 4/4: Backfilling created_by_id for existing documents...")

    connection = op.get_bind()

    # Get total count of documents that need backfilling
    result = connection.execute(
        sa.text("""
            SELECT COUNT(*) FROM documents WHERE created_by_id IS NULL
        """)
    )
    total_count = result.scalar()

    if total_count == 0:
        print("  No documents need backfilling. Skipping.")
        return

    print(f"  Total documents to backfill: {total_count:,}")

    processed = 0
    batch_num = 0

    while processed < total_count:
        batch_num += 1

        # Update a batch of documents using a subquery to limit the update
        # We use ctid (tuple identifier) for efficient batching in PostgreSQL
        result = connection.execute(
            sa.text("""
                UPDATE documents
                SET created_by_id = searchspaces.user_id
                FROM searchspaces
                WHERE documents.search_space_id = searchspaces.id
                AND documents.created_by_id IS NULL
                AND documents.id IN (
                    SELECT d.id FROM documents d
                    WHERE d.created_by_id IS NULL
                    LIMIT :batch_size
                )
            """),
            {"batch_size": BATCH_SIZE},
        )

        rows_updated = result.rowcount
        if rows_updated == 0:
            # No more rows to update
            break

        processed += rows_updated
        progress_pct = min(100.0, (processed / total_count) * 100)

        # Print progress with carriage return for in-place update
        sys.stdout.write(
            f"\r  Progress: {processed:,}/{total_count:,} documents ({progress_pct:.1f}%) - Batch {batch_num}"
        )
        sys.stdout.flush()

    # Final newline after progress
    print()
    print(f"  Done: Backfilled {processed:,} documents.")


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
