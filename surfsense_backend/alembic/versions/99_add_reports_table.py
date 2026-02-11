"""Add reports table

Revision ID: 99
Revises: 98
Create Date: 2026-02-11

Adds report_status enum and reports table for storing generated Markdown reports.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "99"
down_revision: str | None = "98"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create the report_status enum type
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE report_status AS ENUM ('ready', 'failed');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
        """
    )

    # Create the reports table
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS reports (
            id SERIAL PRIMARY KEY,
            title VARCHAR(500) NOT NULL,
            content TEXT,
            report_metadata JSONB,
            status report_status NOT NULL DEFAULT 'ready',
            report_style VARCHAR(100),
            search_space_id INTEGER NOT NULL
                REFERENCES searchspaces(id) ON DELETE CASCADE,
            thread_id INTEGER
                REFERENCES new_chat_threads(id) ON DELETE SET NULL,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
        );
        """
    )

    # Add indexes
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_reports_status
        ON reports(status);
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_reports_search_space_id
        ON reports(search_space_id);
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_reports_thread_id
        ON reports(thread_id);
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_reports_created_at
        ON reports(created_at);
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_reports_created_at")
    op.execute("DROP INDEX IF EXISTS ix_reports_thread_id")
    op.execute("DROP INDEX IF EXISTS ix_reports_search_space_id")
    op.execute("DROP INDEX IF EXISTS ix_reports_status")
    op.execute("DROP TABLE IF EXISTS reports")
    op.execute("DROP TYPE IF EXISTS report_status")

