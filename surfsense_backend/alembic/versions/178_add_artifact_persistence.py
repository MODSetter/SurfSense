"""Add dedicated artifact persistence.

Revision ID: 178
Revises: 177
"""

from collections.abc import Sequence

from alembic import op

revision: str = "178"
down_revision: str | None = "177"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # PostgreSQL makes a newly added enum value usable only after commit.
    with op.get_context().autocommit_block():
        op.execute(
            """
            ALTER TYPE documenttype ADD VALUE IF NOT EXISTS 'ARTIFACT'
            """
        )
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
        CREATE TYPE artifact_file_role AS ENUM ('primary', 'preview')
        """
    )
    op.execute(
        """
        CREATE TABLE artifacts (
            id SERIAL PRIMARY KEY,
            document_id INTEGER NOT NULL
                REFERENCES documents(id) ON DELETE CASCADE,
            workspace_id INTEGER NOT NULL
                REFERENCES workspaces(id) ON DELETE CASCADE,
            thread_id INTEGER
                REFERENCES new_chat_threads(id) ON DELETE SET NULL,
            created_by_id UUID
                REFERENCES "user"(id) ON DELETE SET NULL,
            format VARCHAR NOT NULL,
            generation INTEGER NOT NULL DEFAULT 1,
            created_by_tool_call_id VARCHAR(255),
            updated_by_tool_call_id VARCHAR(255),
            metadata JSONB,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_artifacts_document_id UNIQUE (document_id),
            CONSTRAINT ck_artifacts_generation_positive CHECK (generation > 0)
        )
        """
    )
    for statement in (
        "CREATE INDEX ix_artifacts_workspace_id ON artifacts(workspace_id)",
        "CREATE INDEX ix_artifacts_thread_id ON artifacts(thread_id)",
        "CREATE INDEX ix_artifacts_created_by_id ON artifacts(created_by_id)",
        "CREATE INDEX ix_artifacts_created_at ON artifacts(created_at)",
        "CREATE INDEX ix_artifacts_updated_at ON artifacts(updated_at)",
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
        "CREATE INDEX ix_artifact_files_artifact_id ON artifact_files(artifact_id)"
    )
    op.execute(
        "CREATE INDEX ix_artifact_files_created_at ON artifact_files(created_at)"
    )


def downgrade() -> None:
    for action in ("create", "read", "update", "delete"):
        op.execute(
            f"""
            UPDATE workspace_roles
            SET permissions = array_remove(permissions, 'artifacts:{action}')
            """
        )
    op.execute("DROP TABLE artifact_files")
    op.execute("DROP TABLE artifacts")
    op.execute("DROP TYPE artifact_file_role")
