"""45_add_updated_at_to_documents

Revision ID: 45
Revises: 44
Create Date: 2025-12-12

Adds updated_at field to documents table to track when documents
are updated by indexers, processors, or editor. Includes an index
for efficient time-based filtering.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "45"
down_revision: str | None = "44"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema - Add updated_at field with index to documents."""
    connection = op.get_bind()
    inspector = inspect(connection)
    columns = [col["name"] for col in inspector.get_columns("documents")]

    if "updated_at" not in columns:
        op.add_column(
            "documents",
            sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
        )
        op.create_index(
            "ix_documents_updated_at",
            "documents",
            ["updated_at"],
        )


def downgrade() -> None:
    """Downgrade schema - Remove updated_at field and index."""
    connection = op.get_bind()
    inspector = inspect(connection)
    columns = [col["name"] for col in inspector.get_columns("documents")]

    if "updated_at" in columns:
        op.drop_index("ix_documents_updated_at", table_name="documents", if_exists=True)
        op.drop_column("documents", "updated_at")
