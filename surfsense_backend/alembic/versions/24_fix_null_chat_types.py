"""Fix NULL chat types by setting them to QNA

Revision ID: 24
Revises: 23

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "24"
down_revision: str | None = "23"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def table_exists(table_name: str) -> bool:
    """Check if a table exists in the database."""
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = :table_name)"
        ),
        {"table_name": table_name},
    )
    return result.scalar()


def upgrade() -> None:
    """
    Fix any chats with NULL type values by setting them to QNA.
    This handles edge cases from previous migrations where type values were not properly migrated.
    """
    # Skip if chats table doesn't exist (fresh database)
    if not table_exists("chats"):
        return

    # Update any NULL type values to QNA (the default chat type)
    op.execute(
        """
        UPDATE chats
        SET type = 'QNA'
        WHERE type IS NULL
        """
    )


def downgrade() -> None:
    """
    No downgrade necessary - we can't restore NULL values as we don't know which ones were NULL.
    """
    pass
