"""Add Electric SQL replication for chat_comment_mentions table

Revision ID: 71
Revises: 70

Enables Electric SQL replication for the chat_comment_mentions table to support
real-time live updates for mentions.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "71"
down_revision: str | None = "70"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Enable Electric SQL replication for chat_comment_mentions table."""
    op.execute("ALTER TABLE chat_comment_mentions REPLICA IDENTITY FULL;")

    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_publication_tables 
                WHERE pubname = 'electric_publication_default' 
                AND tablename = 'chat_comment_mentions'
            ) THEN
                ALTER PUBLICATION electric_publication_default ADD TABLE chat_comment_mentions;
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    """Remove chat_comment_mentions from Electric SQL replication."""
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_publication_tables 
                WHERE pubname = 'electric_publication_default' 
                AND tablename = 'chat_comment_mentions'
            ) THEN
                ALTER PUBLICATION electric_publication_default DROP TABLE chat_comment_mentions;
            END IF;
        END
        $$;
        """
    )

    op.execute("ALTER TABLE chat_comment_mentions REPLICA IDENTITY DEFAULT;")
