"""43_add_blocknote_fields_to_documents

Revision ID: 43
Revises: 42
Create Date: 2025-11-30

Adds fields for live document editing:
- blocknote_document: JSONB editor state
- content_needs_reindexing: Flag for regenerating chunks/summary
- last_edited_at: Last edit timestamp
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = "43"
down_revision: str | None = "42"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema - Add BlockNote fields (idempotent)."""

    conn = op.get_bind()
    inspector = inspect(conn)
    existing_cols = {c["name"] for c in inspector.get_columns("documents")}

    # Add blocknote_document (JSONB) if doest not exist
    if "blocknote_document" not in existing_cols:
        op.add_column(
            "documents",
            sa.Column(
                "blocknote_document",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=True,
            ),
        )

    # Add content_needs_reindexing (boolean) if doest not exist
    if "content_needs_reindexing" not in existing_cols:
        op.add_column(
            "documents",
            sa.Column(
                "content_needs_reindexing",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )

    # Add last_edited_at (timestamp with tz) if doest not exist
    if "last_edited_at" not in existing_cols:
        op.add_column(
            "documents",
            sa.Column("last_edited_at", sa.TIMESTAMP(timezone=True), nullable=True),
        )

    # NOTE: We intentionally do NOT import or queue Celery tasks here.
    # Running background jobs during migrations causes hard-to-debug failures.
    # After running migrations, trigger the backfill task manually (instructions below).


def downgrade() -> None:
    """Downgrade schema - Remove BlockNote fields (only if present)."""

    conn = op.get_bind()
    inspector = inspect(conn)
    existing_cols = {c["name"] for c in inspector.get_columns("documents")}

    if "last_edited_at" in existing_cols:
        op.drop_column("documents", "last_edited_at")
    if "content_needs_reindexing" in existing_cols:
        op.drop_column("documents", "content_needs_reindexing")
    if "blocknote_document" in existing_cols:
        op.drop_column("documents", "blocknote_document")
