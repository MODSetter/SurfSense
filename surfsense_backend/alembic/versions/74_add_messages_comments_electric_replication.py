"""Add new_chat_messages and chat_comments to Electric SQL publication

Revision ID: 74
Revises: 73

Enables real-time sync for chat messages and comments via Electric SQL.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "74"
down_revision: str | None = "73"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add new_chat_messages and chat_comments to Electric SQL replication."""
    # Set REPLICA IDENTITY FULL for Electric SQL sync
    op.execute("ALTER TABLE new_chat_messages REPLICA IDENTITY FULL;")
    op.execute("ALTER TABLE chat_comments REPLICA IDENTITY FULL;")

    # Add new_chat_messages to Electric publication
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_publication_tables 
                WHERE pubname = 'electric_publication_default' 
                AND tablename = 'new_chat_messages'
            ) THEN
                ALTER PUBLICATION electric_publication_default ADD TABLE new_chat_messages;
            END IF;
        END
        $$;
        """
    )

    # Add chat_comments to Electric publication
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_publication_tables 
                WHERE pubname = 'electric_publication_default' 
                AND tablename = 'chat_comments'
            ) THEN
                ALTER PUBLICATION electric_publication_default ADD TABLE chat_comments;
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    """Remove new_chat_messages and chat_comments from Electric SQL replication."""
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_publication_tables 
                WHERE pubname = 'electric_publication_default' 
                AND tablename = 'new_chat_messages'
            ) THEN
                ALTER PUBLICATION electric_publication_default DROP TABLE new_chat_messages;
            END IF;
        END
        $$;
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_publication_tables 
                WHERE pubname = 'electric_publication_default' 
                AND tablename = 'chat_comments'
            ) THEN
                ALTER PUBLICATION electric_publication_default DROP TABLE chat_comments;
            END IF;
        END
        $$;
        """
    )

    # Note: Not reverting REPLICA IDENTITY as it doesn't harm normal operations
