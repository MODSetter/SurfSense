"""46_remove_last_edited_at_from_documents

Revision ID: 46
Revises: 45
Create Date: 2025-12-12

Safely migrates last_edited_at values to updated_at, then removes the
last_edited_at field from documents table since we now use updated_at
to track all document updates (indexers, processors, and editor).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import inspect, text

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "46"
down_revision: str | None = "45"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema - Migrate last_edited_at to updated_at, then remove last_edited_at."""
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [col["name"] for col in inspector.get_columns("documents")]

    if "last_edited_at" in columns:
        # Step 1: Copy last_edited_at values to updated_at where updated_at is NULL
        conn.execute(
            text("""
                UPDATE documents
                SET updated_at = last_edited_at
                WHERE last_edited_at IS NOT NULL
                  AND updated_at IS NULL
            """)
        )

        # Step 2: For documents where both exist, use the most recent timestamp
        conn.execute(
            text("""
                UPDATE documents
                SET updated_at = GREATEST(updated_at, last_edited_at)
                WHERE last_edited_at IS NOT NULL
                  AND updated_at IS NOT NULL
            """)
        )

        # Step 3: Drop the last_edited_at column
        op.drop_column("documents", "last_edited_at")


def downgrade() -> None:
    """Downgrade schema - Re-add last_edited_at field to documents."""
    op.add_column(
        "documents",
        sa.Column("last_edited_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    # Note: We cannot restore the original last_edited_at values after downgrade
    # as that data is merged into updated_at
