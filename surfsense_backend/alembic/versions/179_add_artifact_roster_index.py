"""Index generated artifacts by workspace and originating chat.

Revision ID: 179
Revises: 178
"""

from collections.abc import Sequence

from alembic import op

revision: str = "179"
down_revision: str | None = "178"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_documents_generated_thread_roster "
        "ON documents (workspace_id, ((document_metadata ->> 'thread_id'))) "
        "WHERE (document_metadata ->> 'generated') = 'true'"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_documents_generated_thread_roster")
