"""Add Obsidian connector enums

Revision ID: 78
Revises: 77
Create Date: 2026-01-21

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "78"
down_revision: str | None = "77"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add OBSIDIAN_CONNECTOR to documenttype enum
    op.execute("ALTER TYPE documenttype ADD VALUE IF NOT EXISTS 'OBSIDIAN_CONNECTOR'")

    # Add OBSIDIAN_CONNECTOR to searchsourceconnectortype enum
    op.execute(
        "ALTER TYPE searchsourceconnectortype ADD VALUE IF NOT EXISTS 'OBSIDIAN_CONNECTOR'"
    )


def downgrade() -> None:
    # Note: PostgreSQL doesn't support removing enum values directly.
    # The values will remain in the enum type but won't be used.
    pass
