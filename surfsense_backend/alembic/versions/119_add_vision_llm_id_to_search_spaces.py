"""119_add_vision_llm_id_to_search_spaces

Revision ID: 119
Revises: 118

Adds vision_llm_id column to search_spaces for vision/screenshot analysis
LLM role assignment. Defaults to 0 (Auto mode), same convention as
agent_llm_id and document_summary_llm_id.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "119"
down_revision: str | None = "118"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    existing_columns = [
        col["name"] for col in sa.inspect(conn).get_columns("searchspaces")
    ]

    if "vision_llm_id" not in existing_columns:
        op.add_column(
            "searchspaces",
            sa.Column("vision_llm_id", sa.Integer(), nullable=True, server_default="0"),
        )


def downgrade() -> None:
    op.drop_column("searchspaces", "vision_llm_id")
