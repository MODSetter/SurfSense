"""Add thread_id to podcasts

Revision ID: 82
Revises: 81
Create Date: 2026-01-23

"""

from collections.abc import Sequence

from alembic import op

revision: str = "82"
down_revision: str | None = "81"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add thread_id column to podcasts."""
    op.execute(
        """
        ALTER TABLE podcasts
        ADD COLUMN IF NOT EXISTS thread_id INTEGER
        REFERENCES new_chat_threads(id) ON DELETE SET NULL;
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_podcasts_thread_id
        ON podcasts(thread_id);
        """
    )


def downgrade() -> None:
    """Remove thread_id column from podcasts."""
    op.execute("DROP INDEX IF EXISTS ix_podcasts_thread_id")
    op.execute("ALTER TABLE podcasts DROP COLUMN IF EXISTS thread_id")
