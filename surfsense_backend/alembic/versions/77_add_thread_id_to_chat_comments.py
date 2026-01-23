"""Add thread_id to chat_comments for denormalized Electric subscriptions

This denormalization allows a single Electric SQL subscription per thread
instead of one per message, significantly reducing connection overhead.

Revision ID: 77
Revises: 76
"""

from collections.abc import Sequence

from alembic import op

revision: str = "77"
down_revision: str | None = "76"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add thread_id column to chat_comments and backfill from messages."""
    # Add the column (nullable initially for backfill)
    op.execute(
        """
        ALTER TABLE chat_comments
        ADD COLUMN IF NOT EXISTS thread_id INTEGER;
        """
    )

    # Backfill thread_id from the related message
    op.execute(
        """
        UPDATE chat_comments c
        SET thread_id = m.thread_id
        FROM new_chat_messages m
        WHERE c.message_id = m.id
        AND c.thread_id IS NULL;
        """
    )

    # Make it NOT NULL after backfill
    op.execute(
        """
        ALTER TABLE chat_comments
        ALTER COLUMN thread_id SET NOT NULL;
        """
    )

    # Add FK constraint
    op.execute(
        """
        ALTER TABLE chat_comments
        ADD CONSTRAINT fk_chat_comments_thread_id
        FOREIGN KEY (thread_id) REFERENCES new_chat_threads(id) ON DELETE CASCADE;
        """
    )

    # Add index for efficient Electric subscriptions by thread
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_chat_comments_thread_id ON chat_comments(thread_id)"
    )


def downgrade() -> None:
    """Remove thread_id column from chat_comments."""
    op.execute("DROP INDEX IF EXISTS idx_chat_comments_thread_id")
    op.execute(
        "ALTER TABLE chat_comments DROP CONSTRAINT IF EXISTS fk_chat_comments_thread_id"
    )
    op.execute("ALTER TABLE chat_comments DROP COLUMN IF EXISTS thread_id")
