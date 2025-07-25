"""Add LogLevel and LogStatus enums and logs table

Revision ID: 12
Revises: 11
"""

from collections.abc import Sequence

from sqlalchemy import inspect

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "12"
down_revision: str | None = "11"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema - add LogLevel and LogStatus enums and logs table."""

    # Create LogLevel enum if it doesn't exist
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'loglevel') THEN
                CREATE TYPE loglevel AS ENUM ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL');
            END IF;
        END$$;
    """
    )

    # Create LogStatus enum if it doesn't exist
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'logstatus') THEN
                CREATE TYPE logstatus AS ENUM ('IN_PROGRESS', 'SUCCESS', 'FAILED');
            END IF;
        END$$;
    """
    )

    # Create logs table if it doesn't exist
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS logs (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            level loglevel NOT NULL,
            status logstatus NOT NULL,
            message TEXT NOT NULL,
            source VARCHAR(200),
            log_metadata JSONB DEFAULT '{}',
            search_space_id INTEGER NOT NULL REFERENCES searchspaces(id) ON DELETE CASCADE
        );
    """
    )

    # Get existing indexes
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_indexes = [idx["name"] for idx in inspector.get_indexes("logs")]

    # Create indexes only if they don't already exist
    if "ix_logs_id" not in existing_indexes:
        op.create_index("ix_logs_id", "logs", ["id"])
    if "ix_logs_created_at" not in existing_indexes:
        op.create_index("ix_logs_created_at", "logs", ["created_at"])
    if "ix_logs_level" not in existing_indexes:
        op.create_index("ix_logs_level", "logs", ["level"])
    if "ix_logs_status" not in existing_indexes:
        op.create_index("ix_logs_status", "logs", ["status"])
    if "ix_logs_source" not in existing_indexes:
        op.create_index("ix_logs_source", "logs", ["source"])


def downgrade() -> None:
    """Downgrade schema - remove logs table and enums."""

    # Drop indexes
    op.drop_index("ix_logs_source", table_name="logs")
    op.drop_index("ix_logs_status", table_name="logs")
    op.drop_index("ix_logs_level", table_name="logs")
    op.drop_index("ix_logs_created_at", table_name="logs")
    op.drop_index("ix_logs_id", table_name="logs")

    # Drop logs table
    op.drop_table("logs")

    # Drop enums
    op.execute("DROP TYPE IF EXISTS logstatus")
    op.execute("DROP TYPE IF EXISTS loglevel")
