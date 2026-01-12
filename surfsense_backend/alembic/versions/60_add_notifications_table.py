"""Add notifications table

Revision ID: 60
Revises: 59
"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "60"
down_revision: str | None = "59"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema - add notifications table."""
    # Create notifications table
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS notifications (
            id SERIAL PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
            search_space_id INTEGER REFERENCES searchspaces(id) ON DELETE CASCADE,
            type VARCHAR(50) NOT NULL,
            title VARCHAR(200) NOT NULL,
            message TEXT NOT NULL,
            read BOOLEAN NOT NULL DEFAULT FALSE,
            metadata JSONB DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ
        );
    """
    )

    # Create indexes
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_read", "notifications", ["read"])
    op.create_index("ix_notifications_created_at", "notifications", ["created_at"])
    op.create_index("ix_notifications_user_read", "notifications", ["user_id", "read"])

    # Set REPLICA IDENTITY FULL (required by Electric SQL for replication)
    # This allows Electric SQL to track all column values for updates/deletes
    op.execute("ALTER TABLE notifications REPLICA IDENTITY FULL;")

    # Note: ElectricSQL 1.x dynamically adds tables to the publication when
    # clients subscribe to shapes. No need to manually create publications.


def downgrade() -> None:
    """Downgrade schema - remove notifications table."""
    op.drop_index("ix_notifications_user_read", table_name="notifications")
    op.drop_index("ix_notifications_created_at", table_name="notifications")
    op.drop_index("ix_notifications_read", table_name="notifications")
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_table("notifications")
