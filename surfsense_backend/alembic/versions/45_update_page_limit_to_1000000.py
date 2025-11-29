"""Update page limit to 1,000,000

Revision ID: 45
Revises: 44

Changes:
1. Update default pages_limit from 1000 to 1,000,000 for all users
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "45"
down_revision: str | None = "44"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Update page limits for all users to 1,000,000."""
    # Update all users with the old limit of 1000 to the new limit of 1,000,000
    # This ensures existing users get the increased limit
    op.execute(
        """
        UPDATE "user"
        SET pages_limit = 1000000
        WHERE pages_limit = 1000
        """
    )

    # Also update any users with the even older limit of 500
    op.execute(
        """
        UPDATE "user"
        SET pages_limit = 1000000
        WHERE pages_limit = 500
        """
    )


def downgrade() -> None:
    """Revert page limits back to 1000."""
    op.execute(
        """
        UPDATE "user"
        SET pages_limit = 1000
        WHERE pages_limit = 1000000
        """
    )
