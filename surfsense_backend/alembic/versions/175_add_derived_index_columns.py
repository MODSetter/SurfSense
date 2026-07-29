"""Add the derived-index columns: workspace drift marker + chunk line spans.

``workspaces.last_indexed_revision`` records which store revision the chunk
index was built from; NULL means never indexed, which is exactly what makes the
drift sweep pick a workspace up, so no backfill is wanted.

``chunks.start_line`` / ``chunks.end_line`` are the 1-based inclusive line range
each chunk was cut from. NULL on existing rows: they are re-populated the next
time their document is indexed, and their only consumer (line numbers on search
excerpts) treats NULL as "no line info".

One migration for both tables so the two columns cannot become two Alembic
heads.

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
        "ADD COLUMN IF NOT EXISTS last_indexed_revision VARCHAR(64)"
    )
    op.execute("ALTER TABLE chunks ADD COLUMN IF NOT EXISTS start_line INTEGER")
    op.execute("ALTER TABLE chunks ADD COLUMN IF NOT EXISTS end_line INTEGER")


def downgrade() -> None:
    op.execute("ALTER TABLE chunks DROP COLUMN IF EXISTS end_line")
    op.execute("ALTER TABLE chunks DROP COLUMN IF EXISTS start_line")
    op.execute(
        "ALTER TABLE workspaces DROP COLUMN IF EXISTS last_indexed_revision"
    )
