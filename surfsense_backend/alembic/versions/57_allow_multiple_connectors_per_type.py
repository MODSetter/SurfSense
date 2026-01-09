"""Allow multiple connectors of same type per search space

Revision ID: 57
Revises: 56
Create Date: 2026-01-06 12:00:00.000000

"""

from collections.abc import Sequence

from sqlalchemy import text

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "57"
down_revision: str | None = "56"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    connection = op.get_bind()
    constraint_exists = connection.execute(
        text("""
            SELECT 1 FROM information_schema.table_constraints 
            WHERE table_name='search_source_connectors' 
              AND constraint_type='UNIQUE' 
              AND constraint_name='uq_searchspace_user_connector_type'
        """)
    ).scalar()
    if constraint_exists:
        op.drop_constraint(
            "uq_searchspace_user_connector_type",
            "search_source_connectors",
            type_="unique",
        )


def downgrade() -> None:
    connection = op.get_bind()
    constraint_exists = connection.execute(
        text("""
            SELECT 1 FROM information_schema.table_constraints 
            WHERE table_name='search_source_connectors' 
              AND constraint_type='UNIQUE' 
              AND constraint_name='uq_searchspace_user_connector_type'
        """)
    ).scalar()
    if not constraint_exists:
        op.create_unique_constraint(
            "uq_searchspace_user_connector_type",
            "search_source_connectors",
            ["search_space_id", "user_id", "connector_type"],
        )
