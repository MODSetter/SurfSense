"""Add CONFLUENCE_CONNECTOR to enums

Revision ID: 14
Revises: 13
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "14"
down_revision: str | None = "13"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Safely add 'CONFLUENCE_CONNECTOR' to enum types if missing."""

    # Add to searchsourceconnectortype enum
    op.execute(
        """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_type t
            JOIN pg_enum e ON t.oid = e.enumtypid
            WHERE t.typname = 'searchsourceconnectortype' AND e.enumlabel = 'CONFLUENCE_CONNECTOR'
        ) THEN
            ALTER TYPE searchsourceconnectortype ADD VALUE 'CONFLUENCE_CONNECTOR';
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
            WHERE t.typname = 'documenttype' AND e.enumlabel = 'CONFLUENCE_CONNECTOR'
        ) THEN
            ALTER TYPE documenttype ADD VALUE 'CONFLUENCE_CONNECTOR';
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
