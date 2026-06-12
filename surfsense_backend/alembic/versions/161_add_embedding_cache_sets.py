"""add embedding_cache_sets table for content-addressed embedding reuse

Revision ID: 161
Revises: 160
"""

from collections.abc import Sequence

from alembic import op

revision: str = "161"
down_revision: str | None = "160"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS embedding_cache_sets (
            id SERIAL PRIMARY KEY,
            markdown_sha256 VARCHAR(64) NOT NULL,
            embedding_model VARCHAR(255) NOT NULL,
            embedding_dim INTEGER NOT NULL,
            chunker_kind VARCHAR(8) NOT NULL,
            chunker_version INTEGER NOT NULL,
            storage_backend VARCHAR(32) NOT NULL,
            storage_key TEXT NOT NULL,
            size_bytes BIGINT NOT NULL,
            chunk_count INTEGER NOT NULL DEFAULT 0,
            times_reused BIGINT NOT NULL DEFAULT 0,
            last_used_at TIMESTAMP WITH TIME ZONE NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_embedding_cache_sets_key
                UNIQUE (markdown_sha256, embedding_model, chunker_kind, chunker_version)
        );
        """
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_embedding_cache_sets_last_used_at "
        "ON embedding_cache_sets(last_used_at);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_embedding_cache_sets_created_at "
        "ON embedding_cache_sets(created_at);"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_embedding_cache_sets_created_at;")
    op.execute("DROP INDEX IF EXISTS ix_embedding_cache_sets_last_used_at;")
    op.execute("DROP TABLE IF EXISTS embedding_cache_sets;")
