"""Add connector schedules table

Revision ID: 23
Revises: 22
"""

from collections.abc import Sequence

from sqlalchemy import inspect

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "23"
down_revision: str | None = "22"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema - add ScheduleType enum and connector_schedules table."""

    # Create ScheduleType enum if it doesn't exist
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'scheduletype') THEN
                CREATE TYPE scheduletype AS ENUM ('HOURLY', 'DAILY', 'WEEKLY', 'CUSTOM');
            END IF;
        END$$;
    """
    )

    # Create connector_schedules table if it doesn't exist
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS connector_schedules (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            connector_id INTEGER NOT NULL REFERENCES search_source_connectors(id) ON DELETE CASCADE,
            search_space_id INTEGER NOT NULL REFERENCES searchspaces(id) ON DELETE CASCADE,
            schedule_type scheduletype NOT NULL,
            cron_expression VARCHAR(100),
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            last_run_at TIMESTAMPTZ,
            next_run_at TIMESTAMPTZ,
            CONSTRAINT uq_connector_search_space UNIQUE (connector_id, search_space_id)
        );
    """
    )

    # Get existing indexes
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_indexes = [
        idx["name"] for idx in inspector.get_indexes("connector_schedules")
    ]

    # Create indexes only if they don't already exist
    if "ix_connector_schedules_id" not in existing_indexes:
        op.create_index("ix_connector_schedules_id", "connector_schedules", ["id"])
    if "ix_connector_schedules_created_at" not in existing_indexes:
        op.create_index(
            "ix_connector_schedules_created_at", "connector_schedules", ["created_at"]
        )
    if "ix_connector_schedules_connector_id" not in existing_indexes:
        op.create_index(
            "ix_connector_schedules_connector_id", "connector_schedules", ["connector_id"]
        )
    if "ix_connector_schedules_is_active" not in existing_indexes:
        op.create_index(
            "ix_connector_schedules_is_active", "connector_schedules", ["is_active"]
        )
    if "ix_connector_schedules_next_run_at" not in existing_indexes:
        op.create_index(
            "ix_connector_schedules_next_run_at", "connector_schedules", ["next_run_at"]
        )


def downgrade() -> None:
    """Downgrade schema - remove connector_schedules table and enum."""

    # Drop indexes
    op.drop_index("ix_connector_schedules_next_run_at", table_name="connector_schedules")
    op.drop_index("ix_connector_schedules_is_active", table_name="connector_schedules")
    op.drop_index("ix_connector_schedules_connector_id", table_name="connector_schedules")
    op.drop_index("ix_connector_schedules_created_at", table_name="connector_schedules")
    op.drop_index("ix_connector_schedules_id", table_name="connector_schedules")

    # Drop table
    op.drop_table("connector_schedules")

    # Drop enum
    op.execute("DROP TYPE IF EXISTS scheduletype")

