"""Add ClickUp connector enums

Revision ID: '15'
Revises: '14'
Create Date: 2025-07-29 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "15"
down_revision: str | None = "14"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Safely add 'CLICKUP_CONNECTOR' to enum types if missing."""

    # Add to searchsourceconnectortype enum
    op.execute(
        """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_type t
            JOIN pg_enum e ON t.oid = e.enumtypid
            WHERE t.typname = 'searchsourceconnectortype' AND e.enumlabel = 'CLICKUP_CONNECTOR'
        ) THEN
            ALTER TYPE searchsourceconnectortype ADD VALUE 'CLICKUP_CONNECTOR';
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
            WHERE t.typname = 'documenttype' AND e.enumlabel = 'CLICKUP_CONNECTOR'
        ) THEN
            ALTER TYPE documenttype ADD VALUE 'CLICKUP_CONNECTOR';
        END IF;
    END
    $$;
    """
    )


def downgrade() -> None:
    """Remove 'CLICKUP_CONNECTOR' from enum types."""
    # Note: PostgreSQL doesn't support removing enum values directly
    # This would require recreating the enum type, which is complex
    # For now, we'll leave the enum values in place
    pass
