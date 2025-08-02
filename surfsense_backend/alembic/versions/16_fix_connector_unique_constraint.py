"""Fix SearchSourceConnector unique constraint to allow per-user connectors

Revision ID: '16'
Revises: '15'
Create Date: 2025-01-03 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "16"
down_revision: str | None = "15"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Drop unique constraint on connector_type and add composite unique constraint on (user_id, connector_type)."""

    # First, drop the existing unique constraint on connector_type
    # Note: PostgreSQL auto-generates constraint names, so we need to find and drop it
    op.execute(
        """
        DO $$
        DECLARE
            constraint_name TEXT;
        BEGIN
            -- Find the unique constraint on connector_type column
            SELECT tc.constraint_name INTO constraint_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu 
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            WHERE tc.constraint_type = 'UNIQUE'
                AND tc.table_name = 'search_source_connectors'
                AND kcu.column_name = 'connector_type'
                AND tc.table_schema = 'public';
                
            -- Drop the constraint if it exists
            IF constraint_name IS NOT NULL THEN
                EXECUTE format('ALTER TABLE search_source_connectors DROP CONSTRAINT %I', constraint_name);
                RAISE NOTICE 'Dropped unique constraint: %', constraint_name;
            ELSE
                RAISE NOTICE 'No unique constraint found on connector_type column';
            END IF;
        END $$;
        """
    )

    # Add the new composite unique constraint
    op.create_unique_constraint(
        "uq_user_connector_type",
        "search_source_connectors",
        ["user_id", "connector_type"],
    )


def downgrade() -> None:
    """Revert to unique constraint on connector_type only."""

    # Drop the composite unique constraint
    op.drop_constraint(
        "uq_user_connector_type", "search_source_connectors", type_="unique"
    )

    # Add back the unique constraint on connector_type
    # Note: This downgrade will fail if there are duplicate connector_types for different users
    # In that case, manual cleanup would be required
    op.create_unique_constraint(
        None,  # Let PostgreSQL auto-generate the constraint name
        "search_source_connectors",
        ["connector_type"],
    )
