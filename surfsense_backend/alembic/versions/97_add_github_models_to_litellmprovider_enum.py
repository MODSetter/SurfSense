"""Add GITHUB_MODELS to LiteLLMProvider enum

Revision ID: 97
Revises: 96
"""

from collections.abc import Sequence

from alembic import op

revision: str = "97"
down_revision: str | None = "96"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("COMMIT")
    op.execute("ALTER TYPE litellmprovider ADD VALUE IF NOT EXISTS 'GITHUB_MODELS'")


def downgrade() -> None:
    pass
