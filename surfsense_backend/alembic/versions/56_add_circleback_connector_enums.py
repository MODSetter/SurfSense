"""Add Circleback connector enums

Revision ID: 56
Revises: 55
Create Date: 2025-12-30 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "56"
down_revision: str | None = "55"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Safely add 'CIRCLEBACK' to documenttype and 'CIRCLEBACK_CONNECTOR' to searchsourceconnectortype enums if missing."""
    from sqlalchemy import text

    # Get connection and commit current transaction to allow ALTER TYPE
    connection = op.get_bind()
    connection.execute(text("COMMIT"))

    # Add to documenttype enum (must be outside transaction)
    connection.execute(
        text("ALTER TYPE documenttype ADD VALUE IF NOT EXISTS 'CIRCLEBACK'")
    )

    # Add to searchsourceconnectortype enum
    connection.execute(
        text(
            "ALTER TYPE searchsourceconnectortype ADD VALUE IF NOT EXISTS 'CIRCLEBACK_CONNECTOR'"
        )
    )


def downgrade() -> None:
    """Remove 'CIRCLEBACK' and 'CIRCLEBACK_CONNECTOR' from enum types.

    Note: PostgreSQL doesn't support removing enum values directly.
    This would require recreating the enum type, which is complex and risky.
    For now, we'll leave the enum values in place.

    In a production environment with strict downgrade requirements, you would need to:
    1. Create new enum types without the value
    2. Convert all columns to use the new type
    3. Drop the old enum type
    4. Rename the new type to the old name

    This is left as pass to avoid accidental data loss.
    """
    pass
