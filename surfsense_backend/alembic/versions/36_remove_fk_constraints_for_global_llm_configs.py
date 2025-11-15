"""remove_fk_constraints_for_global_llm_configs

Revision ID: 36
Revises: 35
Create Date: 2025-11-13 23:20:12.912741

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "36"
down_revision: str | None = "35"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """
    Remove foreign key constraints on LLM preference columns to allow global configs (negative IDs).

    Global LLM configs use negative IDs and don't exist in the llm_configs table,
    so we need to remove the foreign key constraints that were preventing their use.
    """
    # Drop the foreign key constraints
    op.drop_constraint(
        "user_search_space_preferences_long_context_llm_id_fkey",
        "user_search_space_preferences",
        type_="foreignkey",
    )
    op.drop_constraint(
        "user_search_space_preferences_fast_llm_id_fkey",
        "user_search_space_preferences",
        type_="foreignkey",
    )
    op.drop_constraint(
        "user_search_space_preferences_strategic_llm_id_fkey",
        "user_search_space_preferences",
        type_="foreignkey",
    )


def downgrade() -> None:
    """
    Re-add foreign key constraints (will fail if any negative IDs exist in the table).
    """
    # Re-add the foreign key constraints
    op.create_foreign_key(
        "user_search_space_preferences_long_context_llm_id_fkey",
        "user_search_space_preferences",
        "llm_configs",
        ["long_context_llm_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "user_search_space_preferences_fast_llm_id_fkey",
        "user_search_space_preferences",
        "llm_configs",
        ["fast_llm_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "user_search_space_preferences_strategic_llm_id_fkey",
        "user_search_space_preferences",
        "llm_configs",
        ["strategic_llm_id"],
        ["id"],
        ondelete="SET NULL",
    )
