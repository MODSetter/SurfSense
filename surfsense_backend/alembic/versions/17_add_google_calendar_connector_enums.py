"""Add Google Calendar connector enums

Revision ID: 17
Revises: 16
Create Date: 2024-02-01 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "17"
down_revision: str | None = "16"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Safely add 'GOOGLE_CALENDAR_CONNECTOR' to enum types if missing."""

    # Add to searchsourceconnectortype enum
    op.execute(
        """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_type t
            JOIN pg_enum e ON t.oid = e.enumtypid
            WHERE t.typname = 'searchsourceconnectortype' AND e.enumlabel = 'GOOGLE_CALENDAR_CONNECTOR'
        ) THEN
            ALTER TYPE searchsourceconnectortype ADD VALUE 'GOOGLE_CALENDAR_CONNECTOR';
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
            WHERE t.typname = 'documenttype' AND e.enumlabel = 'GOOGLE_CALENDAR_CONNECTOR'
        ) THEN
            ALTER TYPE documenttype ADD VALUE 'GOOGLE_CALENDAR_CONNECTOR';
        END IF;
    END
    $$;
    """
    )


def downgrade() -> None:
    """Remove 'GOOGLE_CALENDAR_CONNECTOR' from enum types."""

    # Note: PostgreSQL doesn't support removing enum values directly
    # This would require recreating the enrelum type, which is complex
    # For now, we'll leave the enum values in place
    # In a production environment, you might want to implement a more sophisticated downgrade
    pass
