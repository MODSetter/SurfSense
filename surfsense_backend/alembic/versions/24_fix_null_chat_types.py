"""Fix NULL chat types by setting them to QNA

Revision ID: 24
Revises: 23

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "24"
down_revision: str | None = "23"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """
    Fix any chats with NULL type values by setting them to QNA.
    This handles edge cases from previous migrations where type values were not properly migrated.
    """
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
