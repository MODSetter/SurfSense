"""remove_fk_constraints_for_global_llm_configs

Revision ID: 36
Revises: 35
Create Date: 2025-11-13 23:20:12.912741

"""

from collections.abc import Sequence

from sqlalchemy import text

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "36"
down_revision: str | None = "35"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def constraint_exists(connection, table_name: str, constraint_name: str) -> bool:
    """Check if a constraint exists on the given table."""
    result = connection.execute(
        text(
            """
            SELECT 1 FROM information_schema.table_constraints
            WHERE table_name = :table_name AND constraint_name = :constraint_name
            """
        ),
        {"table_name": table_name, "constraint_name": constraint_name},
    )
    return result.fetchone() is not None


def upgrade() -> None:
    """
    Remove foreign key constraints on LLM preference columns to allow global configs (negative IDs).

    Global LLM configs use negative IDs and don't exist in the llm_configs table,
    so we need to remove the foreign key constraints that were preventing their use.
    """
    connection = op.get_bind()

    # Drop the foreign key constraints if they exist
    constraints_to_drop = [
        "user_search_space_preferences_long_context_llm_id_fkey",
        "user_search_space_preferences_fast_llm_id_fkey",
        "user_search_space_preferences_strategic_llm_id_fkey",
    ]

    for constraint_name in constraints_to_drop:
        if constraint_exists(
            connection, "user_search_space_preferences", constraint_name
        ):
            op.drop_constraint(
                constraint_name,
                "user_search_space_preferences",
                type_="foreignkey",
            )
        else:
            print(f"Constraint '{constraint_name}' does not exist. Skipping.")


def downgrade() -> None:
    """
    Re-add foreign key constraints (will fail if any negative IDs exist in the table).
    """
    connection = op.get_bind()

    # Re-add the foreign key constraints if they don't exist
    constraints_to_create = [
        (
            "user_search_space_preferences_long_context_llm_id_fkey",
            "long_context_llm_id",
        ),
        ("user_search_space_preferences_fast_llm_id_fkey", "fast_llm_id"),
        ("user_search_space_preferences_strategic_llm_id_fkey", "strategic_llm_id"),
    ]

    for constraint_name, column_name in constraints_to_create:
        if not constraint_exists(
            connection, "user_search_space_preferences", constraint_name
        ):
            op.create_foreign_key(
                constraint_name,
                "user_search_space_preferences",
                "llm_configs",
                [column_name],
                ["id"],
                ondelete="SET NULL",
            )
        else:
            print(f"Constraint '{constraint_name}' already exists. Skipping.")
