"""Promote the virtual path onto a ``documents.path`` column.

The path a document's content lives at has lived in
``document_metadata->>'virtual_path'`` — a JSON value with no index and no
uniqueness, so resolution was a scan and two rows could silently claim one path
(git's tree cannot). This lands the column the path law resolves on.

Nullable, no backfill: the mistake that killed the ~21-day chunk rewrite was the
mandatory table rewrite, not the column. Rows heal on write (projection upsert,
service save/move, the seeder), so a flagged workspace fills in as it is used.

A **non-unique** partial index ``WHERE path IS NOT NULL`` ships now — instant,
because every existing row is NULL — so path-first resolution is an index hit as
rows heal. The **unique** partial index is deferred to a runbook step run once
the fleet is healed, since a duplicate among unhealed rows would fail the build.

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
