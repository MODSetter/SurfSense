"""Add video_presentations.artifact_id pointing at the delivered Artifact.

Add-only: the Celery task fills it on the next READY commit, and a later
backfill fills existing READY rows. NULL means no Artifact yet (in-flight,
failed, or pre-cutover).

Revision ID: 179
Revises: 178
"""

from collections.abc import Sequence

from alembic import op

revision: str = "179"
down_revision: str | None = "178"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE video_presentations "
        "ADD COLUMN IF NOT EXISTS artifact_id INTEGER "
        "REFERENCES artifacts(id) ON DELETE SET NULL"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE video_presentations DROP COLUMN IF EXISTS artifact_id"
    )
