"""
Add unique constraint for (search_space_id, user_id, name) on search_source_connectors.

Revision ID: 58
Revises: 57
Create Date: 2026-01-06 14:00:00.000000

"""

from collections.abc import Sequence

from sqlalchemy import text

from alembic import op

revision: str = "58"
down_revision: str | None = "57"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    connection = op.get_bind()
    constraint_exists = connection.execute(
        text("""
            SELECT 1 FROM information_schema.table_constraints
            WHERE table_name='search_source_connectors'
              AND constraint_type='UNIQUE'
              AND constraint_name='uq_searchspace_user_connector_name'
        """)
    ).scalar()
    if not constraint_exists:
        op.create_unique_constraint(
            "uq_searchspace_user_connector_name",
            "search_source_connectors",
            ["search_space_id", "user_id", "name"],
        )


def downgrade() -> None:
    connection = op.get_bind()
    constraint_exists = connection.execute(
        text("""
            SELECT 1 FROM information_schema.table_constraints
            WHERE table_name='search_source_connectors'
              AND constraint_type='UNIQUE'
              AND constraint_name='uq_searchspace_user_connector_name'
        """)
    ).scalar()
    if constraint_exists:
        op.drop_constraint(
            "uq_searchspace_user_connector_name",
            "search_source_connectors",
            type_="unique",
        )
