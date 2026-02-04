"""Add DISCORD_JOIN to incentive task type enum

Revision ID: 91
Revises: 90

Changes:
1. Add DISCORD_JOIN value to incentivetasktype enum
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "91"
down_revision: str | None = "90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add DISCORD_JOIN to incentivetasktype enum."""
    op.execute("ALTER TYPE incentivetasktype ADD VALUE IF NOT EXISTS 'DISCORD_JOIN'")


def downgrade() -> None:
    """Remove DISCORD_JOIN from incentivetasktype enum.

    Note: PostgreSQL doesn't support removing values from enums directly.
    This would require recreating the enum type, which is complex and risky.
    For safety, we leave the enum value in place during downgrade.
    """
    pass
