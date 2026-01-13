"""Add chat visibility and created_by_id columns to new_chat_threads

This migration adds:
- ChatVisibility enum (PRIVATE, SEARCH_SPACE)
- visibility column to new_chat_threads table (default: PRIVATE)
- created_by_id column to track who created the chat thread

Revision ID: 61
Revises: 60
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "61"
down_revision: str | None = "60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add visibility and created_by_id columns to new_chat_threads."""

    # Create the ChatVisibility enum type
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'chatvisibility') THEN
                CREATE TYPE chatvisibility AS ENUM ('PRIVATE', 'SEARCH_SPACE');
            END IF;
        END$$;
        """
    )

    # Add visibility column with default value PRIVATE
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'new_chat_threads' AND column_name = 'visibility'
            ) THEN
                ALTER TABLE new_chat_threads 
                ADD COLUMN visibility chatvisibility NOT NULL DEFAULT 'PRIVATE';
            END IF;
        END$$;
        """
    )

    # Create index on visibility column for efficient filtering
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_new_chat_threads_visibility 
        ON new_chat_threads(visibility);
        """
    )

    # Add created_by_id column (nullable to handle existing records)
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'new_chat_threads' AND column_name = 'created_by_id'
            ) THEN
                ALTER TABLE new_chat_threads 
                ADD COLUMN created_by_id UUID REFERENCES "user"(id) ON DELETE SET NULL;
            END IF;
        END$$;
        """
    )

    # Create index on created_by_id column for efficient filtering
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_new_chat_threads_created_by_id 
        ON new_chat_threads(created_by_id);
        """
    )


def downgrade() -> None:
    """Remove visibility and created_by_id columns from new_chat_threads."""

    # Drop indexes
    op.execute("DROP INDEX IF EXISTS ix_new_chat_threads_created_by_id")
    op.execute("DROP INDEX IF EXISTS ix_new_chat_threads_visibility")

    # Drop columns
    op.execute(
        """
        ALTER TABLE new_chat_threads 
        DROP COLUMN IF EXISTS created_by_id;
        """
    )
    op.execute(
        """
        ALTER TABLE new_chat_threads 
        DROP COLUMN IF EXISTS visibility;
        """
    )

    # Drop enum type (only if not used elsewhere)
    op.execute("DROP TYPE IF EXISTS chatvisibility")
