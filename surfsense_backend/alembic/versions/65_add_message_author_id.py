"""Add author_id column to new_chat_messages table

Revision ID: 65
Revises: 64
"""

from collections.abc import Sequence

from alembic import op

revision: str = "65"
down_revision: str | None = "64"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add author_id column to new_chat_messages table."""
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'new_chat_messages' AND column_name = 'author_id'
            ) THEN
                ALTER TABLE new_chat_messages
                ADD COLUMN author_id UUID REFERENCES "user"(id) ON DELETE SET NULL;
                
                CREATE INDEX IF NOT EXISTS ix_new_chat_messages_author_id
                ON new_chat_messages(author_id);
            END IF;
        END$$;
        """
    )


def downgrade() -> None:
    """Remove author_id column from new_chat_messages table."""
    op.execute("DROP INDEX IF EXISTS ix_new_chat_messages_author_id")
    op.execute("ALTER TABLE new_chat_messages DROP COLUMN IF EXISTS author_id")
