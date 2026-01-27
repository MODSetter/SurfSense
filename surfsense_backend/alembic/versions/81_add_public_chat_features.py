"""Add public chat sharing and cloning features to new_chat_threads

Revision ID: 81
Revises: 80
Create Date: 2026-01-23

Adds columns for:
1. Public sharing via tokenized URLs (public_share_token, public_share_enabled)
2. Clone tracking for audit (cloned_from_thread_id, cloned_at)
3. History bootstrap flag for cloned chats (needs_history_bootstrap)
4. Clone pending flag for two-phase clone (clone_pending)
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "81"
down_revision: str | None = "80"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add public sharing and cloning columns to new_chat_threads."""

    op.execute(
        """
        ALTER TABLE new_chat_threads
        ADD COLUMN IF NOT EXISTS public_share_token VARCHAR(64);
        """
    )

    op.execute(
        """
        ALTER TABLE new_chat_threads
        ADD COLUMN IF NOT EXISTS public_share_enabled BOOLEAN NOT NULL DEFAULT FALSE;
        """
    )

    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ix_new_chat_threads_public_share_token
        ON new_chat_threads(public_share_token)
        WHERE public_share_token IS NOT NULL;
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_new_chat_threads_public_share_enabled
        ON new_chat_threads(public_share_enabled)
        WHERE public_share_enabled = TRUE;
        """
    )

    op.execute(
        """
        ALTER TABLE new_chat_threads
        ADD COLUMN IF NOT EXISTS cloned_from_thread_id INTEGER
        REFERENCES new_chat_threads(id) ON DELETE SET NULL;
        """
    )

    op.execute(
        """
        ALTER TABLE new_chat_threads
        ADD COLUMN IF NOT EXISTS cloned_at TIMESTAMP WITH TIME ZONE;
        """
    )

    op.execute(
        """
        ALTER TABLE new_chat_threads
        ADD COLUMN IF NOT EXISTS needs_history_bootstrap BOOLEAN NOT NULL DEFAULT FALSE;
        """
    )

    op.execute(
        """
        ALTER TABLE new_chat_threads
        ADD COLUMN IF NOT EXISTS clone_pending BOOLEAN NOT NULL DEFAULT FALSE;
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_new_chat_threads_cloned_from_thread_id
        ON new_chat_threads(cloned_from_thread_id)
        WHERE cloned_from_thread_id IS NOT NULL;
        """
    )


def downgrade() -> None:
    """Remove public sharing and cloning columns from new_chat_threads."""

    op.execute("DROP INDEX IF EXISTS ix_new_chat_threads_cloned_from_thread_id")
    op.execute("ALTER TABLE new_chat_threads DROP COLUMN IF EXISTS clone_pending")
    op.execute(
        "ALTER TABLE new_chat_threads DROP COLUMN IF EXISTS needs_history_bootstrap"
    )
    op.execute("ALTER TABLE new_chat_threads DROP COLUMN IF EXISTS cloned_at")
    op.execute(
        "ALTER TABLE new_chat_threads DROP COLUMN IF EXISTS cloned_from_thread_id"
    )

    op.execute("DROP INDEX IF EXISTS ix_new_chat_threads_public_share_enabled")
    op.execute("DROP INDEX IF EXISTS ix_new_chat_threads_public_share_token")
    op.execute(
        "ALTER TABLE new_chat_threads DROP COLUMN IF EXISTS public_share_enabled"
    )
    op.execute("ALTER TABLE new_chat_threads DROP COLUMN IF EXISTS public_share_token")
