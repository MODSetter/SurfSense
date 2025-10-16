"""Add SearxNG connector enum value

Revision ID: 27
Revises: 26
Create Date: 2025-01-18 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "27"
down_revision: str | None = "26"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Safely add SEARXNG_API to searchsourceconnectortype enum."""
    op.execute(
        """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_type t
            JOIN pg_enum e ON t.oid = e.enumtypid
            WHERE t.typname = 'searchsourceconnectortype' AND e.enumlabel = 'SEARXNG_API'
        ) THEN
            ALTER TYPE searchsourceconnectortype ADD VALUE 'SEARXNG_API';
        END IF;
    END
    $$;
    """
    )


def downgrade() -> None:
    """Downgrade not supported for enum edits."""
    pass
