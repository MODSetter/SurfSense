"""Add chat_comment_mentions table for @mentions in comments

Revision ID: 67
Revises: 66
"""

from collections.abc import Sequence

from alembic import op

revision: str = "67"
down_revision: str | None = "66"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create chat_comment_mentions table."""
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS chat_comment_mentions (
            id SERIAL PRIMARY KEY,
            comment_id INTEGER NOT NULL REFERENCES chat_comments(id) ON DELETE CASCADE,
            mentioned_user_id UUID NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
            read BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (comment_id, mentioned_user_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_chat_comment_mentions_comment_id ON chat_comment_mentions(comment_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_chat_comment_mentions_user_unread ON chat_comment_mentions(mentioned_user_id) WHERE read = FALSE"
    )


def downgrade() -> None:
    """Drop chat_comment_mentions table."""
    op.execute(
        """
        DROP TABLE IF EXISTS chat_comment_mentions;
        """
    )
