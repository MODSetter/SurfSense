"""Move LLM preferences from user-level to search space level

Revision ID: 40
Revises: 39
Create Date: 2024-11-27

This migration moves LLM preferences (long_context_llm_id, fast_llm_id, strategic_llm_id)
from the user_search_space_preferences table to the searchspaces table itself.

This change supports the RBAC model where LLM preferences are shared by all members
of a search space, rather than being per-user.
"""

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

# revision identifiers, used by Alembic.
revision = "40"
down_revision = "39"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    inspector = inspect(connection)
    columns = [col["name"] for col in inspector.get_columns("searchspaces")]

    # Add LLM preference columns to searchspaces table if they don't exist
    if "long_context_llm_id" not in columns:
        op.add_column(
            "searchspaces",
            sa.Column("long_context_llm_id", sa.Integer(), nullable=True),
        )
    if "fast_llm_id" not in columns:
        op.add_column(
            "searchspaces",
            sa.Column("fast_llm_id", sa.Integer(), nullable=True),
        )
    if "strategic_llm_id" not in columns:
        op.add_column(
            "searchspaces",
            sa.Column("strategic_llm_id", sa.Integer(), nullable=True),
        )

    # Migrate existing preferences from user_search_space_preferences to searchspaces
    # Take the owner's preferences (the user who created the search space)
    connection.execute(
        sa.text("""
            UPDATE searchspaces ss
            SET 
                long_context_llm_id = usp.long_context_llm_id,
                fast_llm_id = usp.fast_llm_id,
                strategic_llm_id = usp.strategic_llm_id
            FROM user_search_space_preferences usp
            WHERE ss.id = usp.search_space_id
            AND ss.user_id = usp.user_id
        """)
    )


def downgrade():
    connection = op.get_bind()
    inspector = inspect(connection)
    columns = [col["name"] for col in inspector.get_columns("searchspaces")]

    # Remove columns only if they exist
    if "strategic_llm_id" in columns:
        op.drop_column("searchspaces", "strategic_llm_id")
    if "fast_llm_id" in columns:
        op.drop_column("searchspaces", "fast_llm_id")
    if "long_context_llm_id" in columns:
        op.drop_column("searchspaces", "long_context_llm_id")
