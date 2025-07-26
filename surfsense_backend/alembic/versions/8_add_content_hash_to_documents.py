"""Add content_hash column to documents table

Revision ID: 8
Revises: 7
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8"
down_revision: str | None = "7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col["name"] for col in inspector.get_columns("documents")]

    # Only add the column if it doesn't already exist
    if "content_hash" not in columns:
        op.add_column(
            "documents", sa.Column("content_hash", sa.String(), nullable=True)
        )

        # Populate the content_hash column
        op.execute(
            """
            UPDATE documents
            SET content_hash = encode(sha256(convert_to(content, 'UTF8')), 'hex')
            WHERE content_hash IS NULL
        """
        )

        op.execute(
            """
            DELETE FROM documents
            WHERE id NOT IN (
                SELECT MIN(id)
                FROM documents
                GROUP BY content_hash
            )
        """
        )

        op.alter_column(
            "documents", "content_hash", existing_type=sa.String(), nullable=False
        )
        op.create_index(
            op.f("ix_documents_content_hash"),
            "documents",
            ["content_hash"],
            unique=False,
        )
        op.create_unique_constraint(
            op.f("uq_documents_content_hash"), "documents", ["content_hash"]
        )
    else:
        print("Column 'content_hash' already exists. Skipping column creation.")


def downgrade() -> None:
    op.drop_constraint(op.f("uq_documents_content_hash"), "documents", type_="unique")
    op.drop_index(op.f("ix_documents_content_hash"), table_name="documents")
    op.drop_column("documents", "content_hash")
