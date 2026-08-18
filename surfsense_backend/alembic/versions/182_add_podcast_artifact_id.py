"""Add podcasts.artifact_id pointing at the delivered Artifact.

Add-only. NULL means no Artifact yet; the render task and the backfill fill it.

Revision ID: 182
Revises: 181
"""

from collections.abc import Sequence

from alembic import op

revision: str = "182"
down_revision: str | None = "181"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE podcasts "
        "ADD COLUMN IF NOT EXISTS artifact_id INTEGER "
        "REFERENCES artifacts(id) ON DELETE SET NULL"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE podcasts DROP COLUMN IF EXISTS artifact_id")
