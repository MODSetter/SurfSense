"""Add MINIMAX to LiteLLMProvider enum

Revision ID: 106
Revises: 105
"""

from collections.abc import Sequence

from alembic import op

revision: str = "106"
down_revision: str | None = "105"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("COMMIT")
    op.execute("ALTER TYPE litellmprovider ADD VALUE IF NOT EXISTS 'MINIMAX'")


def downgrade() -> None:
    pass
