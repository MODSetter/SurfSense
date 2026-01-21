"""Add archived column to notifications table

Revision ID: 73
Revises: 72

Adds an archived boolean column to the notifications table to allow users
to archive inbox items without deleting them.

NOTE: Electric SQL automatically picks up schema changes when REPLICA IDENTITY FULL
is set (which was done in migration 66). We re-affirm it here to ensure replication
continues to work after adding the new column.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "73"
down_revision: str | None = "72"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add archived column to notifications table."""
    # Add the archived column with a default value
    op.execute(
        """
        ALTER TABLE notifications 
        ADD COLUMN IF NOT EXISTS archived BOOLEAN NOT NULL DEFAULT FALSE;
        """
    )
    
    # Create index for archived column
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_notifications_archived ON notifications (archived);"
    )
    
    # Re-affirm REPLICA IDENTITY FULL for Electric SQL after schema change
    # This ensures Electric SQL continues to replicate all columns including the new one
    op.execute("ALTER TABLE notifications REPLICA IDENTITY FULL;")


def downgrade() -> None:
    """Remove archived column from notifications table."""
    op.execute("DROP INDEX IF EXISTS ix_notifications_archived;")
    op.execute("ALTER TABLE notifications DROP COLUMN IF EXISTS archived;")
    # Re-affirm REPLICA IDENTITY FULL after removing the column
    op.execute("ALTER TABLE notifications REPLICA IDENTITY FULL;")

