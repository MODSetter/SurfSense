"""Add Dropbox connector enums

Revision ID: 112
Revises: 111
Create Date: 2026-03-30 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "112"
down_revision: str | None = "111"
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
            WHERE t.typname = 'searchsourceconnectortype' AND e.enumlabel = 'DROPBOX_CONNECTOR'
        ) THEN
            ALTER TYPE searchsourceconnectortype ADD VALUE 'DROPBOX_CONNECTOR';
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
            WHERE t.typname = 'documenttype' AND e.enumlabel = 'DROPBOX_FILE'
        ) THEN
            ALTER TYPE documenttype ADD VALUE 'DROPBOX_FILE';
        END IF;
    END
    $$;
    """
    )


def downgrade() -> None:
    pass
