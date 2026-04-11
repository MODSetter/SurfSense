"""Add memory_md columns to user and searchspaces tables

Revision ID: 121
Revises: 120

Changes:
1. Add memory_md TEXT column to user table (personal memory)
2. Add shared_memory_md TEXT column to searchspaces table (team memory)
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "121"
down_revision: str | None = "120"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column("memory_md", sa.Text(), nullable=True, server_default=""),
    )
    op.add_column(
        "searchspaces",
        sa.Column("shared_memory_md", sa.Text(), nullable=True, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("searchspaces", "shared_memory_md")
    op.drop_column("user", "memory_md")
