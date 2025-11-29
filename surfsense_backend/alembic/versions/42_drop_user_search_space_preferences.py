"""Drop user_search_space_preferences table

Revision ID: 42
Revises: 41
Create Date: 2025-11-28

This table is no longer needed after RBAC implementation:
- LLM preferences are now stored on SearchSpace directly
- User-SearchSpace relationships are handled by SearchSpaceMembership
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "42"
down_revision = "41"
branch_labels = None
depends_on = None


def upgrade():
    # Drop the user_search_space_preferences table
    op.drop_table("user_search_space_preferences")


def downgrade():
    # Recreate the table if rolling back
    op.create_table(
        "user_search_space_preferences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "user_id",
            sa.UUID(),
            sa.ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "search_space_id",
            sa.Integer(),
            sa.ForeignKey("searchspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("long_context_llm_id", sa.Integer(), nullable=True),
        sa.Column("fast_llm_id", sa.Integer(), nullable=True),
        sa.Column("strategic_llm_id", sa.Integer(), nullable=True),
        sa.UniqueConstraint("user_id", "search_space_id", name="uq_user_searchspace"),
    )
