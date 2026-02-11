"""Add report_group_id for report versioning

Revision ID: 100
Revises: 99
Create Date: 2026-02-11

Adds report_group_id column to reports table for grouping report versions.
Reports with the same report_group_id are versions of the same report.
For the first version (v1), report_group_id equals the report's own id.
Migration is idempotent — safe to re-run.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "100"
down_revision: str | None = "99"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add report_group_id column (idempotent)
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'reports' AND column_name = 'report_group_id'
            ) THEN
                ALTER TABLE reports ADD COLUMN report_group_id INTEGER;
            END IF;
        END $$;
        """
    )

    # Backfill existing reports: set report_group_id = id (each is its own v1)
    op.execute(
        """
        UPDATE reports SET report_group_id = id WHERE report_group_id IS NULL;
        """
    )

    # Create index (idempotent)
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_reports_report_group_id
        ON reports(report_group_id);
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_reports_report_group_id")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'reports' AND column_name = 'report_group_id'
            ) THEN
                ALTER TABLE reports DROP COLUMN report_group_id;
            END IF;
        END $$;
        """
    )

