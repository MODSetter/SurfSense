"""Add ElasticSearch connector enums

Revision ID: 31
Revises: 30
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers
revision: str = "31"
down_revision: str | None = "30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add enum values
    op.execute(
        """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_type t
            JOIN pg_enum e ON t.oid = e.enumtypid
            WHERE t.typname = 'searchsourceconnectortype' AND e.enumlabel = 'ELASTICSEARCH_CONNECTOR'
        ) THEN
            ALTER TYPE searchsourceconnectortype ADD VALUE 'ELASTICSEARCH_CONNECTOR';
        END IF;
    END
    $$;
    """
    )
    op.execute(
        """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_type t
            JOIN pg_enum e ON t.oid = e.enumtypid
            WHERE t.typname = 'documenttype' AND e.enumlabel = 'ELASTICSEARCH_CONNECTOR'
        ) THEN
            ALTER TYPE documenttype ADD VALUE 'ELASTICSEARCH_CONNECTOR';
        END IF;
    END
    $$;
    """
    )


def downgrade() -> None:
    """Remove 'ELASTICSEARCH_CONNECTOR' from enum types.

    Note: PostgreSQL does not support removing enum values that may be in use.
    Manual intervention would be required if rollback is necessary:
    1. Delete all rows using ELASTICSEARCH_CONNECTOR
    2. Manually remove the enum value using ALTER TYPE ... DROP VALUE (requires no dependencies)
    """
    pass
