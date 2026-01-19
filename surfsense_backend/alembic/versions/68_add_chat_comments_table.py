"""Add chat_comments table for comments on AI responses

Revision ID: 68
Revises: 67
"""

from collections.abc import Sequence

from alembic import op

revision: str = "68"
down_revision: str | None = "67"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create chat_comments table."""
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS chat_comments (
            id SERIAL PRIMARY KEY,
            message_id INTEGER NOT NULL REFERENCES new_chat_messages(id) ON DELETE CASCADE,
            parent_id INTEGER REFERENCES chat_comments(id) ON DELETE CASCADE,
            author_id UUID REFERENCES "user"(id) ON DELETE SET NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_chat_comments_message_id ON chat_comments(message_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_chat_comments_parent_id ON chat_comments(parent_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_chat_comments_author_id ON chat_comments(author_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_chat_comments_created_at ON chat_comments(created_at)"
    )


def downgrade() -> None:
    """Drop chat_comments table."""
    op.execute(
        """
        DROP TABLE IF EXISTS chat_comments;
        """
    )
