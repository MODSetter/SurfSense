"""Drop legacy user_memories and shared_memories tables

Revision ID: 122
Revises: 121

The old row-per-fact memory system (user_memories, shared_memories tables and
memorycategory enum) is replaced by memory_md / shared_memory_md TEXT columns
added in migration 121.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from app.config import config

revision: str = "122"
down_revision: str | None = "121"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBEDDING_DIM = config.embedding_model_instance.dimension


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS shared_memories CASCADE;")
    op.execute("DROP TABLE IF EXISTS user_memories CASCADE;")
    op.execute("DROP TYPE IF EXISTS memorycategory;")


def downgrade() -> None:
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

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS user_memories (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            user_id UUID NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
            search_space_id INTEGER REFERENCES searchspaces(id) ON DELETE CASCADE,
            memory_text TEXT NOT NULL,
            category memorycategory NOT NULL DEFAULT 'fact',
            embedding vector({EMBEDDING_DIM}),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
        );
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_user_memories_user_id ON user_memories(user_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_user_memories_search_space_id ON user_memories(search_space_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_user_memories_updated_at ON user_memories(updated_at);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_user_memories_category ON user_memories(category);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_user_memories_user_search_space ON user_memories(user_id, search_space_id);")
    op.execute(
        "CREATE INDEX IF NOT EXISTS user_memories_vector_index ON user_memories USING hnsw (embedding public.vector_cosine_ops);"
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS shared_memories (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            search_space_id INTEGER NOT NULL REFERENCES searchspaces(id) ON DELETE CASCADE,
            created_by_id UUID NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
            memory_text TEXT NOT NULL,
            category memorycategory NOT NULL DEFAULT 'fact',
            embedding vector({EMBEDDING_DIM})
        );
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_shared_memories_search_space_id ON shared_memories(search_space_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_shared_memories_updated_at ON shared_memories(updated_at);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_shared_memories_created_by_id ON shared_memories(created_by_id);")
    op.execute(
        "CREATE INDEX IF NOT EXISTS shared_memories_vector_index ON shared_memories USING hnsw (embedding public.vector_cosine_ops);"
    )
