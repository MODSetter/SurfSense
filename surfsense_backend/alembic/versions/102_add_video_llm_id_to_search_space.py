"""Add video_llm_id to searchspaces

Revision ID: 102
Revises: 99
Create Date: 2026-02-27
"""

import sqlalchemy as sa

from alembic import op

revision: str = "102"
down_revision: str | None = "99"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    result = connection.execute(
        sa.text(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'searchspaces'
                  AND column_name = 'video_llm_id'
            )
            """
        )
    )
    if not result.scalar():
        op.add_column(
            "searchspaces",
            sa.Column("video_llm_id", sa.Integer(), nullable=True),
        )


def downgrade() -> None:
    connection = op.get_bind()
    result = connection.execute(
        sa.text(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'searchspaces'
                  AND column_name = 'video_llm_id'
            )
            """
        )
    )
    if result.scalar():
        op.drop_column("searchspaces", "video_llm_id")
