"""Add chat_session_state table for live collaboration

Revision ID: 75
Revises: 74

Creates chat_session_state table to track AI responding state per thread.
Enables real-time sync via Electric SQL for shared chat collaboration.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "75"
down_revision: str | None = "74"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create chat_session_state table with Electric SQL replication."""
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS chat_session_state (
            id SERIAL PRIMARY KEY,
            thread_id INTEGER NOT NULL REFERENCES new_chat_threads(id) ON DELETE CASCADE,
            ai_responding_to_user_id UUID REFERENCES "user"(id) ON DELETE SET NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (thread_id)
        )
        """
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_chat_session_state_thread_id ON chat_session_state(thread_id)"
    )

    op.execute("ALTER TABLE chat_session_state REPLICA IDENTITY FULL;")

    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_publication_tables 
                WHERE pubname = 'electric_publication_default' 
                AND tablename = 'chat_session_state'
            ) THEN
                ALTER PUBLICATION electric_publication_default ADD TABLE chat_session_state;
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    """Drop chat_session_state table and remove from Electric SQL replication."""
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_publication_tables 
                WHERE pubname = 'electric_publication_default' 
                AND tablename = 'chat_session_state'
            ) THEN
                ALTER PUBLICATION electric_publication_default DROP TABLE chat_session_state;
            END IF;
        END
        $$;
        """
    )

    op.execute("DROP TABLE IF EXISTS chat_session_state;")
