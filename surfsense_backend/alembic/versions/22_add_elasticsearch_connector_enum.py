"""Add ElasticSearch connector enums

Revision ID: 22
Revises: 21
Create Date: 2025-10-4 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers
revision: str = "22"
down_revision: str | None = "21"
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
    pass
