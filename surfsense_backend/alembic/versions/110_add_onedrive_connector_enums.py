"""Add OneDrive connector enums

Revision ID: 110
Revises: 109
Create Date: 2026-03-28 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "110"
down_revision: str | None = "109"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_type t
            JOIN pg_enum e ON t.oid = e.enumtypid
            WHERE t.typname = 'searchsourceconnectortype' AND e.enumlabel = 'ONEDRIVE_CONNECTOR'
        ) THEN
            ALTER TYPE searchsourceconnectortype ADD VALUE 'ONEDRIVE_CONNECTOR';
        END IF;
    END
    $$;
    """
    )

    op.execute(
        """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_type t
            JOIN pg_enum e ON t.oid = e.enumtypid
            WHERE t.typname = 'documenttype' AND e.enumlabel = 'ONEDRIVE_FILE'
        ) THEN
            ALTER TYPE documenttype ADD VALUE 'ONEDRIVE_FILE';
        END IF;
    END
    $$;
    """
    )


def downgrade() -> None:
    pass
