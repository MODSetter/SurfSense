"""Add LOCAL_FOLDER_FILE document type and document_versions table

Revision ID: 117
Revises: 116
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "117"
down_revision: str | None = "116"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PUBLICATION_NAME = "zero_publication"


def upgrade() -> None:
    conn = op.get_bind()

    # Add LOCAL_FOLDER_FILE to documenttype enum
    op.execute(
        """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_type t
            JOIN pg_enum e ON t.oid = e.enumtypid
            WHERE t.typname = 'documenttype' AND e.enumlabel = 'LOCAL_FOLDER_FILE'
        ) THEN
            ALTER TYPE documenttype ADD VALUE 'LOCAL_FOLDER_FILE';
        END IF;
    END
    $$;
    """
    )

    # Create document_versions table
    table_exists = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables WHERE table_name = 'document_versions'"
        )
    ).fetchone()
    if not table_exists:
        op.create_table(
            "document_versions",
            sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
            sa.Column("document_id", sa.Integer(), nullable=False),
            sa.Column("version_number", sa.Integer(), nullable=False),
            sa.Column("source_markdown", sa.Text(), nullable=True),
            sa.Column("content_hash", sa.String(), nullable=False),
            sa.Column("title", sa.String(), nullable=True),
            sa.Column(
                "created_at",
                sa.TIMESTAMP(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["document_id"],
                ["documents.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "document_id",
                "version_number",
                name="uq_document_version",
            ),
        )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_document_versions_document_id "
        "ON document_versions (document_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_document_versions_created_at "
        "ON document_versions (created_at)"
    )

    # Add document_versions to Zero publication
    pub_exists = conn.execute(
        sa.text("SELECT 1 FROM pg_publication WHERE pubname = :name"),
        {"name": PUBLICATION_NAME},
    ).fetchone()
    if pub_exists:
        already_in_pub = conn.execute(
            sa.text(
                "SELECT 1 FROM pg_publication_tables "
                "WHERE pubname = :name AND tablename = 'document_versions'"
            ),
            {"name": PUBLICATION_NAME},
        ).fetchone()
        if not already_in_pub:
            op.execute(
                f"ALTER PUBLICATION {PUBLICATION_NAME} ADD TABLE document_versions"
            )


def downgrade() -> None:
    conn = op.get_bind()

    # Remove from publication
    pub_exists = conn.execute(
        sa.text("SELECT 1 FROM pg_publication WHERE pubname = :name"),
        {"name": PUBLICATION_NAME},
    ).fetchone()
    if pub_exists:
        already_in_pub = conn.execute(
            sa.text(
                "SELECT 1 FROM pg_publication_tables "
                "WHERE pubname = :name AND tablename = 'document_versions'"
            ),
            {"name": PUBLICATION_NAME},
        ).fetchone()
        if already_in_pub:
            op.execute(
                f"ALTER PUBLICATION {PUBLICATION_NAME} DROP TABLE document_versions"
            )

    op.execute("DROP INDEX IF EXISTS ix_document_versions_created_at")
    op.execute("DROP INDEX IF EXISTS ix_document_versions_document_id")
    op.execute("DROP TABLE IF EXISTS document_versions")
