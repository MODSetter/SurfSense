"""Promote the virtual path onto a ``documents.path`` column.

Nullable, no backfill; rows heal on write. A non-unique partial index over the
non-NULL rows ships now (instant, since all rows start NULL); the unique index
is a deferred runbook step, once the fleet is healed.

Revision ID: 177
Revises: 176
"""

from collections.abc import Sequence

from alembic import op

revision: str = "177"
down_revision: str | None = "176"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE documents ADD COLUMN IF NOT EXISTS path VARCHAR")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_documents_workspace_path "
        "ON documents (workspace_id, path) WHERE path IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_documents_workspace_path")
    op.execute("ALTER TABLE documents DROP COLUMN IF EXISTS path")
