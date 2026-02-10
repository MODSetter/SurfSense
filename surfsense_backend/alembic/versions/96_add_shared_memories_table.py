"""Add shared_memories table (SUR-152)."""

from collections.abc import Sequence

from alembic import op
from app.config import config

revision: str = "96"
down_revision: str | None = "95"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBEDDING_DIM = config.embedding_model_instance.dimension


def upgrade() -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'shared_memories'
            ) THEN
                CREATE TABLE shared_memories (
                    id SERIAL PRIMARY KEY,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    search_space_id INTEGER NOT NULL REFERENCES searchspaces(id) ON DELETE CASCADE,
                    created_by_id UUID NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
                    memory_text TEXT NOT NULL,
                    category memorycategory NOT NULL DEFAULT 'fact',
                    embedding vector({EMBEDDING_DIM})
                );
            END IF;
        END$$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_indexes
                WHERE tablename = 'shared_memories' AND indexname = 'ix_shared_memories_search_space_id'
            ) THEN
                CREATE INDEX ix_shared_memories_search_space_id ON shared_memories(search_space_id);
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM pg_indexes
                WHERE tablename = 'shared_memories' AND indexname = 'ix_shared_memories_updated_at'
            ) THEN
                CREATE INDEX ix_shared_memories_updated_at ON shared_memories(updated_at);
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM pg_indexes
                WHERE tablename = 'shared_memories' AND indexname = 'ix_shared_memories_created_by_id'
            ) THEN
                CREATE INDEX ix_shared_memories_created_by_id ON shared_memories(created_by_id);
            END IF;
        END$$;
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS shared_memories_vector_index
        ON shared_memories USING hnsw (embedding public.vector_cosine_ops);
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS shared_memories_vector_index;")
    op.execute("DROP INDEX IF EXISTS ix_shared_memories_created_by_id;")
    op.execute("DROP INDEX IF EXISTS ix_shared_memories_updated_at;")
    op.execute("DROP INDEX IF EXISTS ix_shared_memories_search_space_id;")
    op.execute("DROP TABLE IF EXISTS shared_memories CASCADE;")
