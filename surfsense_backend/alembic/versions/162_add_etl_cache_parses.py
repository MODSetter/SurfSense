"""add etl_cache_parses table for content-addressed parse reuse

Revision ID: 162
Revises: 161
"""

from collections.abc import Sequence

from alembic import op

revision: str = "162"
down_revision: str | None = "161"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS etl_cache_parses (
            id SERIAL PRIMARY KEY,
            source_sha256 VARCHAR(64) NOT NULL,
            etl_service VARCHAR(32) NOT NULL,
            mode VARCHAR(16) NOT NULL,
            parser_version INTEGER NOT NULL,
            storage_backend VARCHAR(32) NOT NULL,
            storage_key TEXT NOT NULL,
            size_bytes BIGINT NOT NULL,
            content_type VARCHAR(32) NOT NULL,
            actual_pages INTEGER NOT NULL DEFAULT 0,
            times_reused BIGINT NOT NULL DEFAULT 0,
            last_used_at TIMESTAMP WITH TIME ZONE NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_etl_cache_parses_key
                UNIQUE (source_sha256, etl_service, mode, parser_version)
        );
        """
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_etl_cache_parses_last_used_at "
        "ON etl_cache_parses(last_used_at);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_etl_cache_parses_created_at "
        "ON etl_cache_parses(created_at);"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_etl_cache_parses_created_at;")
    op.execute("DROP INDEX IF EXISTS ix_etl_cache_parses_last_used_at;")
    op.execute("DROP TABLE IF EXISTS etl_cache_parses;")
