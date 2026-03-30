"""add is_public to prompts

Revision ID: 112
Revises: 111
"""

from collections.abc import Sequence

from alembic import op

revision: str = "112"
down_revision: str | None = "111"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE prompts ADD COLUMN IF NOT EXISTS is_public BOOLEAN NOT NULL DEFAULT false"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE prompts DROP COLUMN IF EXISTS is_public")
