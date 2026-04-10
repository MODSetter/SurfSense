"""121_add_enable_vision_llm_to_connectors

Revision ID: 121
Revises: 120
Create Date: 2026-04-09

Adds enable_vision_llm boolean column to search_source_connectors.
Defaults to False so vision LLM image processing is opt-in.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "121"
down_revision: str | None = "120"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    existing_columns = [
        col["name"] for col in sa.inspect(conn).get_columns("search_source_connectors")
    ]

    if "enable_vision_llm" not in existing_columns:
        op.add_column(
            "search_source_connectors",
            sa.Column(
                "enable_vision_llm",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )


def downgrade() -> None:
    op.drop_column("search_source_connectors", "enable_vision_llm")
