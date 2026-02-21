"""101_add_source_markdown_to_documents

Revision ID: 101
Revises: 100
Create Date: 2026-02-17

Adds source_markdown column to documents.  All existing rows start as NULL
and get populated lazily by the editor route when a user first opens them.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "101"
down_revision: str | None = "100"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    existing_columns = [
        col["name"] for col in sa.inspect(conn).get_columns("documents")
    ]

    if "source_markdown" not in existing_columns:
        op.add_column(
            "documents",
            sa.Column("source_markdown", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("documents", "source_markdown")
