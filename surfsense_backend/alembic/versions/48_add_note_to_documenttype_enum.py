"""48_add_note_to_documenttype_enum

Revision ID: 48
Revises: 47
Adds NOTE document type to support user-created BlockNote documents.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "48"
down_revision: str | None = "47"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Define the ENUM type name and the new value
ENUM_NAME = "documenttype"
NEW_VALUE = "NOTE"


def upgrade() -> None:
    """Safely add 'NOTE' to documenttype enum if missing."""
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
    """
    Downgrade logic not implemented since PostgreSQL
    does not support removing enum values.
    """
    pass
