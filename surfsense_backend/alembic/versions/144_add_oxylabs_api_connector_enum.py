"""Add Oxylabs API connector enum

Revision ID: 144
Revises: 143
Create Date: 2026-05-29 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "144"
down_revision: str | None = "143"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Safely add 'OXYLABS_API' to the searchsourceconnectortype enum if missing."""
    op.execute(
        """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_type t
            JOIN pg_enum e ON t.oid = e.enumtypid
            WHERE t.typname = 'searchsourceconnectortype' AND e.enumlabel = 'OXYLABS_API'
        ) THEN
            ALTER TYPE searchsourceconnectortype ADD VALUE 'OXYLABS_API';
        END IF;
    END
    $$;
    """
    )


def downgrade() -> None:
    """Postgres cannot drop enum values; no-op (matches existing enum migrations)."""
    pass
