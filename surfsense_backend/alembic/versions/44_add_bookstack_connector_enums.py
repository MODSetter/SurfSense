"""Add BOOKSTACK_CONNECTOR to enums

Revision ID: 44
Revises: 43
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "44"
down_revision: str | None = "43"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Safely add 'BOOKSTACK_CONNECTOR' to enum types if missing."""

    # Add to searchsourceconnectortype enum
    op.execute(
        """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_type t
            JOIN pg_enum e ON t.oid = e.enumtypid
            WHERE t.typname = 'searchsourceconnectortype' AND e.enumlabel = 'BOOKSTACK_CONNECTOR'
        ) THEN
            ALTER TYPE searchsourceconnectortype ADD VALUE 'BOOKSTACK_CONNECTOR';
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
            WHERE t.typname = 'documenttype' AND e.enumlabel = 'BOOKSTACK_CONNECTOR'
        ) THEN
            ALTER TYPE documenttype ADD VALUE 'BOOKSTACK_CONNECTOR';
        END IF;
    END
    $$;
    """
    )


def downgrade() -> None:
    """
    Downgrade logic not implemented since PostgreSQL
    does not support removing enum values.
    """
    pass
