"""Add ZENDESK_CONNECTOR to enums

Revision ID: 15
Revises: 14
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "15"
down_revision: str | None = "14"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Safely add 'ZENDESK_CONNECTOR' to enum types if missing."""

    # Add to searchsourceconnectortype enum
    op.execute(
        """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_type t
            JOIN pg_enum e ON t.oid = e.enumtypid
            WHERE t.typname = 'searchsourceconnectortype' AND e.enumlabel = 'ZENDESK_CONNECTOR'
        ) THEN
            ALTER TYPE searchsourceconnectortype ADD VALUE 'ZENDESK_CONNECTOR';
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
            WHERE t.typname = 'documenttype' AND e.enumlabel = 'ZENDESK_CONNECTOR'
        ) THEN
            ALTER TYPE documenttype ADD VALUE 'ZENDESK_CONNECTOR';
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
