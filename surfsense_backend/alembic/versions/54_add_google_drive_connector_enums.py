"""Add Google Drive connector enums

Revision ID: 54
Revises: 53
Create Date: 2025-12-28 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "54"
down_revision: str | None = "53"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Safely add 'GOOGLE_DRIVE_CONNECTOR' to enum types if missing."""

    # Add to searchsourceconnectortype enum
    op.execute(
        """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_type t
            JOIN pg_enum e ON t.oid = e.enumtypid
            WHERE t.typname = 'searchsourceconnectortype' AND e.enumlabel = 'GOOGLE_DRIVE_CONNECTOR'
        ) THEN
            ALTER TYPE searchsourceconnectortype ADD VALUE 'GOOGLE_DRIVE_CONNECTOR';
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
            WHERE t.typname = 'documenttype' AND e.enumlabel = 'GOOGLE_DRIVE_CONNECTOR'
        ) THEN
            ALTER TYPE documenttype ADD VALUE 'GOOGLE_DRIVE_CONNECTOR';
        END IF;
    END
    $$;
    """
    )


def downgrade() -> None:
    """Remove 'GOOGLE_DRIVE_CONNECTOR' from enum types.

    Note: PostgreSQL doesn't support removing enum values directly.
    This would require recreating the enum type, which is complex and risky.
    For now, we'll leave the enum values in place.

    In a production environment with strict downgrade requirements, you would need to:
    1. Create new enum types without the value
    2. Convert all columns to use the new type
    3. Drop the old enum type
    4. Rename the new type to the old name

    This is left as pass to avoid accidental data loss.
    """
    pass
