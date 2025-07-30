"""Add ClickUp connector enums

Revision ID: 15_add_clickup_connector_enums
Revises: 14_add_confluence_connector_enums
Create Date: 2025-07-29 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "15_add_clickup_connector_enums"
down_revision: Union[str, None] = "14_add_confluence_connector_enums"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Safely add 'CLICKUP_CONNECTOR' to enum types if missing."""

    # Add to searchsourceconnectortype enum
    op.execute(
        """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_type t
            JOIN pg_enum e ON t.oid = e.enumtypid
            WHERE t.typname = 'searchsourceconnectortype' AND e.enumlabel = 'CLICKUP_CONNECTOR'
        ) THEN
            ALTER TYPE searchsourceconnectortype ADD VALUE 'CLICKUP_CONNECTOR';
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
            WHERE t.typname = 'documenttype' AND e.enumlabel = 'CLICKUP_CONNECTOR'
        ) THEN
            ALTER TYPE documenttype ADD VALUE 'CLICKUP_CONNECTOR';
        END IF;
    END
    $$;
    """
    )


def downgrade() -> None:
    """Remove 'CLICKUP_CONNECTOR' from enum types."""
    # Note: PostgreSQL doesn't support removing enum values directly
    # This would require recreating the enum type, which is complex
    # For now, we'll leave the enum values in place
    pass
