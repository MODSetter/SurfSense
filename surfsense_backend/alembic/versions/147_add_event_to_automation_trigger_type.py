"""Add 'event' to automation_trigger_type enum

Revision ID: 147
Revises: 146
Create Date: 2026-05-29

Adds the ``event`` value to the ``automation_trigger_type`` enum so automations
can be triggered by published domain events, alongside the existing
``schedule`` triggers.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "147"
down_revision: str | None = "146"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ENUM_NAME = "automation_trigger_type"
NEW_VALUE = "event"


def upgrade() -> None:
    """Safely add 'event' to automation_trigger_type enum if missing."""
    op.execute(
        f"""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_type t
            JOIN pg_enum e ON t.oid = e.enumtypid
            WHERE t.typname = '{ENUM_NAME}' AND e.enumlabel = '{NEW_VALUE}'
        ) THEN
            ALTER TYPE {ENUM_NAME} ADD VALUE '{NEW_VALUE}';
        END IF;
    END
    $$;
    """
    )


def downgrade() -> None:
    """No-op: PostgreSQL does not support removing enum values."""
    pass
