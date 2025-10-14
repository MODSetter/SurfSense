"""Associate SearchSourceConnector with SearchSpace instead of User

Revision ID: '23'
Revises: '22'

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "23"
down_revision: str | None = "22"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """
    Add search_space_id to SearchSourceConnector and update unique constraint.

    Changes:
    1. Add search_space_id column (nullable initially)
    2. Populate search_space_id with user's first search space
    3. Make search_space_id NOT NULL
    4. Add foreign key constraint
    5. Drop old unique constraint (user_id, connector_type)
    6. Add new unique constraint (search_space_id, user_id, connector_type)
    """

    from sqlalchemy import inspect

    conn = op.get_bind()
    inspector = inspect(conn)

    # Get existing columns
    columns = [col["name"] for col in inspector.get_columns("search_source_connectors")]

    # Step 1: Add search_space_id column as nullable first (if it doesn't exist)
    if "search_space_id" not in columns:
        op.add_column(
            "search_source_connectors",
            sa.Column("search_space_id", sa.Integer(), nullable=True),
        )

    # Step 2: Populate search_space_id with each user's first search space
    # This ensures existing connectors are assigned to a valid search space
    op.execute(
        """
        UPDATE search_source_connectors ssc
        SET search_space_id = (
            SELECT id 
            FROM searchspaces ss 
            WHERE ss.user_id = ssc.user_id 
            ORDER BY ss.created_at ASC 
            LIMIT 1
        )
        WHERE search_space_id IS NULL
        """
    )

    # Step 3: Make search_space_id NOT NULL
    op.alter_column(
        "search_source_connectors",
        "search_space_id",
        nullable=False,
    )

    # Step 4: Add foreign key constraint (if it doesn't exist)
    foreign_keys = [
        fk["name"] for fk in inspector.get_foreign_keys("search_source_connectors")
    ]
    if "fk_search_source_connectors_search_space_id" not in foreign_keys:
        op.create_foreign_key(
            "fk_search_source_connectors_search_space_id",
            "search_source_connectors",
            "searchspaces",
            ["search_space_id"],
            ["id"],
            ondelete="CASCADE",
        )

    # Step 5: Drop the old unique constraint (user_id, connector_type) if it exists
    unique_constraints = [
        uc["name"]
        for uc in inspector.get_unique_constraints("search_source_connectors")
    ]
    if "uq_user_connector_type" in unique_constraints:
        op.drop_constraint(
            "uq_user_connector_type",
            "search_source_connectors",
            type_="unique",
        )

    # Step 6: Create new unique constraint (search_space_id, user_id, connector_type) if it doesn't exist
    if "uq_searchspace_user_connector_type" not in unique_constraints:
        op.create_unique_constraint(
            "uq_searchspace_user_connector_type",
            "search_source_connectors",
            ["search_space_id", "user_id", "connector_type"],
        )


def downgrade() -> None:
    """
    Revert SearchSourceConnector association back to User only.

    WARNING: This downgrade may result in data loss if multiple connectors
    of the same type exist for a user across different search spaces.
    """

    from sqlalchemy import inspect

    conn = op.get_bind()
    inspector = inspect(conn)

    # Get existing constraints and columns
    unique_constraints = [
        uc["name"]
        for uc in inspector.get_unique_constraints("search_source_connectors")
    ]
    foreign_keys = [
        fk["name"] for fk in inspector.get_foreign_keys("search_source_connectors")
    ]
    columns = [col["name"] for col in inspector.get_columns("search_source_connectors")]

    # Step 1: Drop the new unique constraint if it exists
    if "uq_searchspace_user_connector_type" in unique_constraints:
        op.drop_constraint(
            "uq_searchspace_user_connector_type",
            "search_source_connectors",
            type_="unique",
        )

    # Step 2: Recreate the old unique constraint (user_id, connector_type) if it doesn't exist
    # NOTE: This will fail if there are duplicate (user_id, connector_type) combinations
    # Manual cleanup may be required before downgrading
    if "uq_user_connector_type" not in unique_constraints:
        op.create_unique_constraint(
            "uq_user_connector_type",
            "search_source_connectors",
            ["user_id", "connector_type"],
        )

    # Step 3: Drop the foreign key constraint if it exists
    if "fk_search_source_connectors_search_space_id" in foreign_keys:
        op.drop_constraint(
            "fk_search_source_connectors_search_space_id",
            "search_source_connectors",
            type_="foreignkey",
        )

    # Step 4: Drop the search_space_id column if it exists
    if "search_space_id" in columns:
        op.drop_column("search_source_connectors", "search_space_id")
