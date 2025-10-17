"""Add BAIDU_SEARCH_API to searchsourceconnectortype enum

Revision ID: 30
Revises: 29

Changes:
1. Add BAIDU_SEARCH_API value to searchsourceconnectortype enum
2. Add BAIDU_SEARCH_API value to documenttype enum for consistency
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "30"
down_revision: str | None = "29"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add BAIDU_SEARCH_API to searchsourceconnectortype and documenttype enums."""

    # Add BAIDU_SEARCH_API to searchsourceconnectortype enum
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_type t 
                JOIN pg_enum e ON t.oid = e.enumtypid  
                WHERE t.typname = 'searchsourceconnectortype' AND e.enumlabel = 'BAIDU_SEARCH_API'
            ) THEN
                ALTER TYPE searchsourceconnectortype ADD VALUE 'BAIDU_SEARCH_API';
            END IF;
        END
        $$;
        """
    )

    # Add BAIDU_SEARCH_API to documenttype enum for consistency
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_type t 
                JOIN pg_enum e ON t.oid = e.enumtypid  
                WHERE t.typname = 'documenttype' AND e.enumlabel = 'BAIDU_SEARCH_API'
            ) THEN
                ALTER TYPE documenttype ADD VALUE 'BAIDU_SEARCH_API';
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    """
    Downgrade is not supported for enum values in PostgreSQL.

    Removing enum values can break existing data and is generally not safe.
    To remove these values, you would need to:
    1. Remove all references to BAIDU_SEARCH_API in the database
    2. Recreate the enum type without BAIDU_SEARCH_API
    3. Reapply all other enum values

    This is intentionally left as a no-op for safety.
    """
    pass
