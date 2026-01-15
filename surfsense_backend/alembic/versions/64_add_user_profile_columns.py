"""Add display_name and avatar_url columns to user table

This migration adds:
- display_name column for user's full name from OAuth
- avatar_url column for user's profile picture URL from OAuth

Revision ID: 64
Revises: 63
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "64"
down_revision: str | None = "63"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add display_name and avatar_url columns to user table."""

    # Add display_name column (nullable for existing users)
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'user' AND column_name = 'display_name'
            ) THEN
                ALTER TABLE "user" 
                ADD COLUMN display_name VARCHAR;
            END IF;
        END$$;
        """
    )

    # Add avatar_url column (nullable for existing users)
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'user' AND column_name = 'avatar_url'
            ) THEN
                ALTER TABLE "user" 
                ADD COLUMN avatar_url VARCHAR;
            END IF;
        END$$;
        """
    )


def downgrade() -> None:
    """Remove display_name and avatar_url columns from user table."""

    op.execute(
        """
        ALTER TABLE "user" 
        DROP COLUMN IF EXISTS avatar_url;
        """
    )
    op.execute(
        """
        ALTER TABLE "user" 
        DROP COLUMN IF EXISTS display_name;
        """
    )
