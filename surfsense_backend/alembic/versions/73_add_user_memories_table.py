"""Add user_memories table for AI memory feature

Revision ID: 73
Revises: 72
Create Date: 2026-01-20

This migration adds the user_memories table which enables Claude-like memory
functionality - allowing the AI to remember facts, preferences, and context
about users across conversations.
"""

from collections.abc import Sequence

from alembic import op
from app.config import config

# revision identifiers, used by Alembic.
revision: str = "73"
down_revision: str | None = "72"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Get embedding dimension from config
EMBEDDING_DIM = config.embedding_model_instance.dimension


def upgrade() -> None:
    """Create user_memories table and MemoryCategory enum."""

    # Create the MemoryCategory enum type
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'memorycategory') THEN
                CREATE TYPE memorycategory AS ENUM (
                    'preference',
                    'fact',
                    'instruction',
                    'context'
                );
            END IF;
        END$$;
        """
    )

    # Create user_memories table
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'user_memories'
            ) THEN
                CREATE TABLE user_memories (
                    id SERIAL PRIMARY KEY,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    user_id UUID NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
                    search_space_id INTEGER REFERENCES searchspaces(id) ON DELETE CASCADE,
                    memory_text TEXT NOT NULL,
                    category memorycategory NOT NULL DEFAULT 'fact',
                    embedding vector({EMBEDDING_DIM}),
                    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
                );
            END IF;
        END$$;
        """
    )

    # Create indexes for efficient querying
    op.execute(
        """
        DO $$
        BEGIN
            -- Index on user_id for filtering memories by user
            IF NOT EXISTS (
                SELECT 1 FROM pg_indexes
                WHERE tablename = 'user_memories' AND indexname = 'ix_user_memories_user_id'
            ) THEN
                CREATE INDEX ix_user_memories_user_id ON user_memories(user_id);
            END IF;

            -- Index on search_space_id for filtering memories by search space
            IF NOT EXISTS (
                SELECT 1 FROM pg_indexes
                WHERE tablename = 'user_memories' AND indexname = 'ix_user_memories_search_space_id'
            ) THEN
                CREATE INDEX ix_user_memories_search_space_id ON user_memories(search_space_id);
            END IF;

            -- Index on updated_at for ordering by recency
            IF NOT EXISTS (
                SELECT 1 FROM pg_indexes
                WHERE tablename = 'user_memories' AND indexname = 'ix_user_memories_updated_at'
            ) THEN
                CREATE INDEX ix_user_memories_updated_at ON user_memories(updated_at);
            END IF;

            -- Index on category for filtering by memory type
            IF NOT EXISTS (
                SELECT 1 FROM pg_indexes
                WHERE tablename = 'user_memories' AND indexname = 'ix_user_memories_category'
            ) THEN
                CREATE INDEX ix_user_memories_category ON user_memories(category);
            END IF;

            -- Composite index for common query pattern (user + search space)
            IF NOT EXISTS (
                SELECT 1 FROM pg_indexes
                WHERE tablename = 'user_memories' AND indexname = 'ix_user_memories_user_search_space'
            ) THEN
                CREATE INDEX ix_user_memories_user_search_space ON user_memories(user_id, search_space_id);
            END IF;
        END$$;
        """
    )

    # Create vector index for semantic search
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS user_memories_vector_index
        ON user_memories USING hnsw (embedding public.vector_cosine_ops);
        """
    )


def downgrade() -> None:
    """Drop user_memories table and MemoryCategory enum."""

    # Drop the table
    op.execute("DROP TABLE IF EXISTS user_memories CASCADE;")

    # Drop the enum type
    op.execute("DROP TYPE IF EXISTS memorycategory;")
