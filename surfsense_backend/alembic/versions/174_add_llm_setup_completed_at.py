"""Add workspaces.llm_setup_completed_at for first-run vs. recovery onboarding.

No backfill: NULL is correct for every existing row. Configured workspaces
self-heal via lazy stamping on their next status read (which fires while still
``ready``, before they could reach ``needs_setup``); a blanket
``SET ... = created_at`` would misclassify abandoned and global-only workspaces.

Revision ID: 174
Revises: 173
"""

from collections.abc import Sequence

from alembic import op

revision: str = "174"
down_revision: str | None = "173"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE workspaces "
        "ADD COLUMN IF NOT EXISTS llm_setup_completed_at TIMESTAMPTZ"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE workspaces DROP COLUMN IF EXISTS llm_setup_completed_at")
