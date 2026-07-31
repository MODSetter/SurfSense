"""Add workspaces.knowledge_store_enabled for the progressive git-native flip.

Per-workspace switch between the old write path and the git-native one; the
global KNOWLEDGE_STORE_ENABLED env stays the master kill switch (a workspace
is git-native only when both are on). Default false: every workspace keeps
the old path until its seed passes parity and it is flipped explicitly.

Revision ID: 175
Revises: 174
"""

from collections.abc import Sequence

from alembic import op

revision: str = "175"
down_revision: str | None = "174"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE workspaces "
        "ADD COLUMN IF NOT EXISTS knowledge_store_enabled BOOLEAN "
        "NOT NULL DEFAULT FALSE"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE workspaces DROP COLUMN IF EXISTS knowledge_store_enabled")
