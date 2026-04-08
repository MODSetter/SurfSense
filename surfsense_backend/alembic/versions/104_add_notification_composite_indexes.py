"""104_add_notification_composite_indexes

Revision ID: 104
Revises: 103
Create Date: 2026-03-10

Add composite indexes on the notifications table to speed up the
most common query patterns:
  - Unread count by user/category: (user_id, read, type, created_at)
  - Notification list by user/space: (user_id, search_space_id, created_at)
  - Single-column index on type (for category filtering)
  - Single-column index on search_space_id (for space filtering)
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "104"
down_revision: str | None = "103"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_notifications_user_read_type_created",
        "notifications",
        ["user_id", "read", "type", "created_at"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_notifications_user_space_created",
        "notifications",
        ["user_id", "search_space_id", "created_at"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_notifications_type",
        "notifications",
        ["type"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_notifications_search_space_id",
        "notifications",
        ["search_space_id"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index("ix_notifications_search_space_id", table_name="notifications")
    op.drop_index("ix_notifications_type", table_name="notifications")
    op.drop_index("ix_notifications_user_space_created", table_name="notifications")
    op.drop_index("ix_notifications_user_read_type_created", table_name="notifications")
