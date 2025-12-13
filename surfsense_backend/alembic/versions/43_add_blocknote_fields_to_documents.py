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

# revision identifiers, used by Alembic.
revision: str = "43"
down_revision: str | None = "42"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema - Add BlockNote fields and trigger population task."""

    # Get existing columns to avoid duplicates
    conn = op.get_bind()
    existing_columns = [
        col["name"] for col in sa.inspect(conn).get_columns("documents")
    ]

    # Add the columns if they don't exist
    if "blocknote_document" not in existing_columns:
        op.add_column(
            "documents",
            sa.Column(
                "blocknote_document",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=True,
            ),
        )

    if "content_needs_reindexing" not in existing_columns:
        op.add_column(
            "documents",
            sa.Column(
                "content_needs_reindexing",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )

    if "last_edited_at" not in existing_columns:
        op.add_column(
            "documents",
            sa.Column("last_edited_at", sa.TIMESTAMP(timezone=True), nullable=True),
        )

    # Trigger the Celery task to populate blocknote_document for existing documents
    try:
        from app.tasks.celery_tasks.blocknote_migration_tasks import (
            populate_blocknote_for_documents_task,
        )

        # Queue the task to run asynchronously
        populate_blocknote_for_documents_task.apply_async()
        print(
            "✓ Queued Celery task to populate blocknote_document for existing documents"
        )
    except Exception as e:
        print(f"⚠ Warning: Could not queue blocknote population task: {e}")
        print("  You can manually trigger it later with:")
        print(
            "  celery -A app.celery_app call app.tasks.celery_tasks.blocknote_migration_tasks.populate_blocknote_for_documents_task"
        )


def downgrade() -> None:
    """Downgrade schema - Remove BlockNote fields."""
    op.drop_column("documents", "last_edited_at")
    op.drop_column("documents", "content_needs_reindexing")
    op.drop_column("documents", "blocknote_document")
