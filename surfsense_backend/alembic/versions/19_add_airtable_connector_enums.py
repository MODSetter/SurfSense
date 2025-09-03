"""Add AIRTABLE_CONNECTOR to enums

Revision ID: 19
Revises: 18
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "19"
down_revision = "18"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade schema - add AIRTABLE_CONNECTOR to enums."""
    # Add to searchsourceconnectortype enum
    op.execute(
        """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_type t
            JOIN pg_enum e ON t.oid = e.enumtypid
            WHERE t.typname = 'searchsourceconnectortype' AND e.enumlabel = 'AIRTABLE_CONNECTOR'
        ) THEN
            ALTER TYPE searchsourceconnectortype ADD VALUE 'AIRTABLE_CONNECTOR';
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
            WHERE t.typname = 'documenttype' AND e.enumlabel = 'AIRTABLE_CONNECTOR'
        ) THEN
            ALTER TYPE documenttype ADD VALUE 'AIRTABLE_CONNECTOR';
        END IF;
    END
    $$;
    """
    )


def downgrade() -> None:
    """Downgrade schema - remove AIRTABLE_CONNECTOR from enums."""
    pass
