"""Add Webcrawler connector enums

Revision ID: 38
Revises: 37
Create Date: 2025-11-17 17:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "38"
down_revision: str | None = "37"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Safely add 'WEBCRAWLER_CONNECTOR' to enum types if missing."""

    # Add to searchsourceconnectortype enum
    op.execute(
        """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_type t
            JOIN pg_enum e ON t.oid = e.enumtypid
            WHERE t.typname = 'searchsourceconnectortype' AND e.enumlabel = 'WEBCRAWLER_CONNECTOR'
        ) THEN
            ALTER TYPE searchsourceconnectortype ADD VALUE 'WEBCRAWLER_CONNECTOR';
        END IF;
    END
    $$;
    """
    )

    # Add to documenttype enum
    op.execute(
        """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_type t
            JOIN pg_enum e ON t.oid = e.enumtypid
            WHERE t.typname = 'documenttype' AND e.enumlabel = 'CRAWLED_URL'
        ) THEN
            ALTER TYPE documenttype ADD VALUE 'CRAWLED_URL';
        END IF;
    END
    $$;
    """
    )


def downgrade() -> None:
    """Remove 'WEBCRAWLER_CONNECTOR' from enum types."""
    pass
