"""Add workspace_git_remotes for connect-your-own push.

One destination per workspace in v1 (unique on workspace_id). Disconnect
deletes the row; the worker no-ops when none exist.

Revision ID: 190
Revises: 189
"""

from collections.abc import Sequence

from alembic import op

revision: str = "190"
down_revision: str | None = "189"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS workspace_git_remotes (
            id SERIAL PRIMARY KEY,
            workspace_id INTEGER NOT NULL
                REFERENCES workspaces(id) ON DELETE CASCADE,
            provider VARCHAR(16) NOT NULL,
            url VARCHAR(512) NOT NULL,
            branch VARCHAR(255) NOT NULL DEFAULT 'main',
            installation_id VARCHAR(64),
            token TEXT,
            last_pushed_revision VARCHAR(64),
            last_pushed_at TIMESTAMPTZ,
            last_push_error TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_workspace_git_remotes_workspace UNIQUE (workspace_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_workspace_git_remotes_id "
        "ON workspace_git_remotes(id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_workspace_git_remotes_created_at "
        "ON workspace_git_remotes(created_at)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS workspace_git_remotes")
