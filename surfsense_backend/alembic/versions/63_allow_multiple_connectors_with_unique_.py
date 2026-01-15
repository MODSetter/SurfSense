"""allow_multiple_connectors_with_unique_names

Revision ID: 63
Revises: 62
Create Date: 2026-01-13 12:23:31.481643

"""

from collections.abc import Sequence

from sqlalchemy import text

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "63"
down_revision: str | None = "62"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    connection = op.get_bind()

    # Check if old constraint exists before trying to drop it
    old_constraint_exists = connection.execute(
        text("""
            SELECT 1 FROM information_schema.table_constraints 
            WHERE table_name='search_source_connectors' 
              AND constraint_type='UNIQUE' 
              AND constraint_name='uq_searchspace_user_connector_type'
        """)
    ).scalar()

    if old_constraint_exists:
        op.drop_constraint(
            "uq_searchspace_user_connector_type",
            "search_source_connectors",
            type_="unique",
        )

    # Check if new constraint already exists before creating it
    new_constraint_exists = connection.execute(
        text("""
            SELECT 1 FROM information_schema.table_constraints 
            WHERE table_name='search_source_connectors' 
              AND constraint_type='UNIQUE' 
              AND constraint_name='uq_searchspace_user_connector_type_name'
        """)
    ).scalar()

    if not new_constraint_exists:
        op.create_unique_constraint(
            "uq_searchspace_user_connector_type_name",
            "search_source_connectors",
            ["search_space_id", "user_id", "connector_type", "name"],
        )


def downgrade() -> None:
    """Downgrade schema."""
    connection = op.get_bind()

    # Check if new constraint exists before trying to drop it
    new_constraint_exists = connection.execute(
        text("""
            SELECT 1 FROM information_schema.table_constraints 
            WHERE table_name='search_source_connectors' 
              AND constraint_type='UNIQUE' 
              AND constraint_name='uq_searchspace_user_connector_type_name'
        """)
    ).scalar()

    if new_constraint_exists:
        op.drop_constraint(
            "uq_searchspace_user_connector_type_name",
            "search_source_connectors",
            type_="unique",
        )

    # Check if old constraint already exists before creating it
    old_constraint_exists = connection.execute(
        text("""
            SELECT 1 FROM information_schema.table_constraints 
            WHERE table_name='search_source_connectors' 
              AND constraint_type='UNIQUE' 
              AND constraint_name='uq_searchspace_user_connector_type'
        """)
    ).scalar()

    if not old_constraint_exists:
        op.create_unique_constraint(
            "uq_searchspace_user_connector_type",
            "search_source_connectors",
            ["search_space_id", "user_id", "connector_type"],
        )
