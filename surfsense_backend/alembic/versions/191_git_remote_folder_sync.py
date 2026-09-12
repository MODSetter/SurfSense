"""Folder-sync stamps on workspace_git_remotes.

Revision ID: 191
Revises: 190
"""

from collections.abc import Sequence

from alembic import op

revision: str = "191"
down_revision: str | None = "190"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE workspace_git_remotes
            ADD COLUMN IF NOT EXISTS sourcepath VARCHAR(255) NOT NULL DEFAULT '',
            ADD COLUMN IF NOT EXISTS last_remote_sha VARCHAR(64),
            ADD COLUMN IF NOT EXISTS last_local_revision VARCHAR(64),
            ADD COLUMN IF NOT EXISTS last_synced_at TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS last_error_code VARCHAR(32),
            ADD COLUMN IF NOT EXISTS last_conflict_paths TEXT
        """
    )
    op.execute(
        "ALTER TABLE workspace_git_remotes ALTER COLUMN sourcepath DROP DEFAULT"
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE workspace_git_remotes
            DROP COLUMN IF EXISTS sourcepath,
            DROP COLUMN IF EXISTS last_remote_sha,
            DROP COLUMN IF EXISTS last_local_revision,
            DROP COLUMN IF EXISTS last_synced_at,
            DROP COLUMN IF EXISTS last_error_code,
            DROP COLUMN IF EXISTS last_conflict_paths
        """
    )
