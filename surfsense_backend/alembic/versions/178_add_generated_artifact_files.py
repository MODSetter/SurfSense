"""Add generated artifact files and their display role.

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
    # PostgreSQL cannot use a newly added enum value until its transaction
    # commits. The following partial index compares the enum directly, so make
    # the enum addition visible before creating the index.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE document_file_kind ADD VALUE IF NOT EXISTS 'GENERATED'")
    op.execute(
        "ALTER TABLE document_files "
        "ADD COLUMN IF NOT EXISTS role VARCHAR(16) NOT NULL DEFAULT 'primary'"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_document_files_generated_role "
        "ON document_files (document_id, role) "
        "WHERE kind = 'GENERATED'"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_documents_generated_thread_roster "
        "ON documents (workspace_id, ((document_metadata ->> 'thread_id'))) "
        "WHERE (document_metadata ->> 'generated') = 'true'"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_documents_generated_thread_roster")
    op.execute("DROP INDEX IF EXISTS uq_document_files_generated_role")
    op.execute("ALTER TABLE document_files DROP COLUMN IF EXISTS role")
