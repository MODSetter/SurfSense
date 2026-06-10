"""add document_files table for stored original uploads

Revision ID: 152
Revises: 151
"""

from collections.abc import Sequence

from alembic import op

revision: str = "152"
down_revision: str | None = "151"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The enum type must precede the table that references it.
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_type WHERE typname = 'document_file_kind'
            ) THEN
                CREATE TYPE document_file_kind AS ENUM (
                    'ORIGINAL', 'REDACTED', 'FILLED_FORM'
                );
            END IF;
        END
        $$;
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS document_files (
            id SERIAL PRIMARY KEY,
            document_id INTEGER NOT NULL
                REFERENCES documents(id) ON DELETE CASCADE,
            search_space_id INTEGER NOT NULL
                REFERENCES searchspaces(id) ON DELETE CASCADE,
            kind document_file_kind NOT NULL DEFAULT 'ORIGINAL',
            storage_backend VARCHAR(32) NOT NULL,
            storage_key TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            mime_type TEXT,
            size_bytes BIGINT NOT NULL,
            checksum_sha256 VARCHAR(64),
            created_by_id UUID
                REFERENCES "user"(id) ON DELETE SET NULL,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
        );
        """
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_document_files_document_id "
        "ON document_files(document_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_document_files_search_space_id "
        "ON document_files(search_space_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_document_files_kind ON document_files(kind);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_document_files_created_by_id "
        "ON document_files(created_by_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_document_files_created_at "
        "ON document_files(created_at);"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_document_files_created_at;")
    op.execute("DROP INDEX IF EXISTS ix_document_files_created_by_id;")
    op.execute("DROP INDEX IF EXISTS ix_document_files_kind;")
    op.execute("DROP INDEX IF EXISTS ix_document_files_search_space_id;")
    op.execute("DROP INDEX IF EXISTS ix_document_files_document_id;")
    op.execute("DROP TABLE IF EXISTS document_files;")
    op.execute("DROP TYPE IF EXISTS document_file_kind;")
