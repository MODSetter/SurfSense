"""Add unique_identifier_hash column to documents table

Revision ID: 29
Revises: 28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "29"
down_revision: str | None = "28"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col["name"] for col in inspector.get_columns("documents")]

    # Only add the column if it doesn't already exist
    if "unique_identifier_hash" not in columns:
        op.add_column(
            "documents",
            sa.Column("unique_identifier_hash", sa.String(), nullable=True),
        )
        op.create_index(
            op.f("ix_documents_unique_identifier_hash"),
            "documents",
            ["unique_identifier_hash"],
            unique=False,
        )
        op.create_unique_constraint(
            op.f("uq_documents_unique_identifier_hash"),
            "documents",
            ["unique_identifier_hash"],
        )
    else:
        print(
            "Column 'unique_identifier_hash' already exists. Skipping column creation."
        )


def downgrade() -> None:
    op.drop_constraint(
        op.f("uq_documents_unique_identifier_hash"), "documents", type_="unique"
    )
    op.drop_index(op.f("ix_documents_unique_identifier_hash"), table_name="documents")
    op.drop_column("documents", "unique_identifier_hash")
