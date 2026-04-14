"""124_add_ai_file_sort_enabled

Revision ID: 124
Revises: 123
Create Date: 2026-04-14

Adds ai_file_sort_enabled boolean column to searchspaces.
Defaults to False so AI file sorting is opt-in per search space.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "124"
down_revision: str | None = "123"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    existing_columns = [
        col["name"] for col in sa.inspect(conn).get_columns("searchspaces")
    ]

    if "ai_file_sort_enabled" not in existing_columns:
        op.add_column(
            "searchspaces",
            sa.Column(
                "ai_file_sort_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )


def downgrade() -> None:
    op.drop_column("searchspaces", "ai_file_sort_enabled")
