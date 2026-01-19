"""Add Electric SQL replication for chat_comments table

Revision ID: 71
Revises: 70

Enables Electric SQL replication for the chat_comments table to support
real-time live updates for comments in chat threads.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "71"
down_revision: str | None = "70"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Enable Electric SQL replication for chat_comments table."""
    # Set REPLICA IDENTITY FULL (required by Electric SQL for replication)
    op.execute("ALTER TABLE chat_comments REPLICA IDENTITY FULL;")

    # Add chat_comments to Electric SQL publication for replication
    op.execute(
        """
        DO $$
        BEGIN
            -- Add chat_comments if not already added
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
    """Remove chat_comments from Electric SQL replication."""
    # Remove chat_comments from publication
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

    # Reset REPLICA IDENTITY to default
    op.execute("ALTER TABLE chat_comments REPLICA IDENTITY DEFAULT;")
