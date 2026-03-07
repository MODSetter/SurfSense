"""102_add_enable_summary_to_connectors

Revision ID: 102
Revises: 101
Create Date: 2026-02-26

Adds enable_summary boolean column to search_source_connectors.
Defaults to False for all existing and new connectors so LLM-based
summary generation is opt-in.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "102"
down_revision: str | None = "101"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    existing_columns = [
        col["name"] for col in sa.inspect(conn).get_columns("search_source_connectors")
    ]

    if "enable_summary" not in existing_columns:
        op.add_column(
            "search_source_connectors",
            sa.Column(
                "enable_summary",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )


def downgrade() -> None:
    op.drop_column("search_source_connectors", "enable_summary")
