"""Add REDDIT_FOLLOW to incentive task type enum

Revision ID: 83
Revises: 82

Changes:
1. Add REDDIT_FOLLOW value to incentivetasktype enum
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "83"
down_revision: str | None = "82"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add REDDIT_FOLLOW to incentivetasktype enum."""
    op.execute("ALTER TYPE incentivetasktype ADD VALUE IF NOT EXISTS 'REDDIT_FOLLOW'")


def downgrade() -> None:
    """Remove REDDIT_FOLLOW from incentivetasktype enum.

    Note: PostgreSQL doesn't support removing values from enums directly.
    This would require recreating the enum type, which is complex and risky.
    For safety, we leave the enum value in place during downgrade.
    """
    pass
