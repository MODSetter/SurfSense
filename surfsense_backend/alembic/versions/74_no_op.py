"""No-op migration for Composio support

Revision ID: 74
Revises: 73
Create Date: 2026-01-21

NOTE: This migration is a no-op since Composio is not supported yet.
"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "74"
down_revision: str | None = "73"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """No-op upgrade for Composio support."""
    pass


def downgrade() -> None:
    """No-op downgrade for Composio support.

    Note: PostgreSQL does not support removing enum values directly.
    """
    pass
