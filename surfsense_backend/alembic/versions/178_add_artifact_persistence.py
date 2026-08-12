"""Add dedicated artifact persistence.

Revision ID: 178
Revises: 177
"""

from collections.abc import Sequence

from alembic import op
from app.config import config

revision: str = "178"
down_revision: str | None = "177"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBEDDING_DIM = config.embedding_model_instance.dimension


def upgrade() -> None:
    for action in ("create", "read", "update", "delete"):
        op.execute(
            f"""
            UPDATE workspace_roles
            SET permissions = array_append(permissions, 'artifacts:{action}')
            WHERE 'documents:{action}' = ANY(permissions)
              AND NOT ('artifacts:{action}' = ANY(permissions))
            """
        )
    op.execute(
        """
        CREATE TYPE artifact_file_role AS ENUM ('primary', 'preview', 'source')
        """
    )
    op.execute(
        f"""
        CREATE TABLE artifacts (
            id SERIAL PRIMARY KEY,
            workspace_id INTEGER NOT NULL
                REFERENCES workspaces(id) ON DELETE CASCADE,
            thread_id INTEGER
                REFERENCES new_chat_threads(id) ON DELETE SET NULL,
            created_by_id UUID
                REFERENCES "user"(id) ON DELETE SET NULL,
            title VARCHAR NOT NULL,
            format VARCHAR NOT NULL,
            markdown_representation TEXT NOT NULL,
            path VARCHAR NOT NULL,
            markdown_hash VARCHAR(64) NOT NULL,
            markdown_embedding vector({EMBEDDING_DIM}),
            version INTEGER NOT NULL DEFAULT 1,
            indexed_version INTEGER,
            indexing_status VARCHAR(32) NOT NULL DEFAULT 'pending',
            indexing_error TEXT,
            created_by_tool_call_id VARCHAR(255),
            updated_by_tool_call_id VARCHAR(255),
            metadata JSONB,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_artifacts_version_positive CHECK (version > 0),
            CONSTRAINT ck_artifacts_indexed_version_valid CHECK (
                indexed_version IS NULL
                OR (
                    indexed_version > 0
                    AND indexed_version <= version
                )
            ),
            CONSTRAINT uq_artifacts_workspace_path UNIQUE (workspace_id, path)
        )
        """
    )
    for statement in (
        "CREATE INDEX ix_artifacts_workspace_id ON artifacts(workspace_id)",
        "CREATE INDEX ix_artifacts_thread_id ON artifacts(thread_id)",
        "CREATE INDEX ix_artifacts_created_by_id ON artifacts(created_by_id)",
        "CREATE INDEX ix_artifacts_markdown_hash ON artifacts(markdown_hash)",
        "CREATE INDEX ix_artifacts_indexing_status ON artifacts(indexing_status)",
        "CREATE INDEX ix_artifacts_created_at ON artifacts(created_at)",
        "CREATE INDEX ix_artifacts_updated_at ON artifacts(updated_at)",
        "CREATE INDEX artifacts_vector_index ON artifacts USING hnsw "
        "(markdown_embedding public.vector_cosine_ops)",
        "CREATE INDEX artifacts_search_index ON artifacts USING gin "
        "(to_tsvector('english', markdown_representation))",
    ):
        op.execute(statement)
    op.execute(
        """
        CREATE TABLE artifact_files (
            id SERIAL PRIMARY KEY,
            artifact_id INTEGER NOT NULL
                REFERENCES artifacts(id) ON DELETE CASCADE,
            role artifact_file_role NOT NULL,
            storage_backend VARCHAR(32) NOT NULL,
            storage_key VARCHAR NOT NULL,
            original_filename VARCHAR NOT NULL,
            mime_type VARCHAR NOT NULL,
            size_bytes BIGINT NOT NULL,
            checksum_sha256 VARCHAR(64) NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_artifact_files_artifact_role
                UNIQUE (artifact_id, role),
            CONSTRAINT uq_artifact_files_storage_key UNIQUE (storage_key),
            CONSTRAINT ck_artifact_files_size_positive CHECK (size_bytes > 0)
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_artifact_files_artifact_id "
        "ON artifact_files(artifact_id)"
    )
    op.execute(
        "CREATE INDEX ix_artifact_files_created_at ON artifact_files(created_at)"
    )
    op.execute(
        f"""
        CREATE TABLE artifact_chunks (
            id SERIAL PRIMARY KEY,
            artifact_id INTEGER NOT NULL
                REFERENCES artifacts(id) ON DELETE CASCADE,
            content TEXT NOT NULL,
            embedding vector({EMBEDDING_DIM}),
            position INTEGER NOT NULL DEFAULT 0,
            start_line INTEGER,
            end_line INTEGER,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_artifact_chunks_position_nonnegative
                CHECK (position >= 0),
            CONSTRAINT ck_artifact_chunks_line_range CHECK (
                (start_line IS NULL AND end_line IS NULL)
                OR (
                    start_line IS NOT NULL
                    AND end_line IS NOT NULL
                    AND start_line > 0
                    AND end_line >= start_line
                )
            )
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_artifact_chunks_artifact_id "
        "ON artifact_chunks(artifact_id)"
    )
    op.execute(
        "CREATE INDEX ix_artifact_chunks_created_at "
        "ON artifact_chunks(created_at)"
    )
    op.execute(
        "CREATE INDEX artifact_chunks_vector_index "
        "ON artifact_chunks USING hnsw (embedding public.vector_cosine_ops)"
    )
    op.execute(
        "CREATE INDEX artifact_chunks_search_index "
        "ON artifact_chunks USING gin (to_tsvector('english', content))"
    )


def downgrade() -> None:
    for action in ("create", "read", "update", "delete"):
        op.execute(
            f"""
            UPDATE workspace_roles
            SET permissions = array_remove(permissions, 'artifacts:{action}')
            """
        )
    op.execute("DROP TABLE artifact_chunks")
    op.execute("DROP TABLE artifact_files")
    op.execute("DROP TABLE artifacts")
    op.execute("DROP TYPE artifact_file_role")
