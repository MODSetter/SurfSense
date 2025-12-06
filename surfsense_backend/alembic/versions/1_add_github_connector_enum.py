"""Add GITHUB_CONNECTOR to SearchSourceConnectorType enum

Revision ID: 1
Revises:
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Ensure the enum type exists
    op.execute(
        """
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'searchsourceconnectortype') THEN
        CREATE TYPE searchsourceconnectortype AS ENUM(
            'SERPER_API', 
            'TAVILY_API', 
            'SLACK_CONNECTOR', 
            'NOTION_CONNECTOR'
        );
    END IF;
END$$;
"""
    )

    # Add the new enum value if it doesn't exist
    op.execute(
        """
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_enum
        WHERE enumlabel = 'GITHUB_CONNECTOR'
        AND enumtypid = (
            SELECT oid FROM pg_type WHERE typname = 'searchsourceconnectortype'
        )
    ) THEN
        ALTER TYPE searchsourceconnectortype ADD VALUE 'GITHUB_CONNECTOR';
    END IF;
END$$;
"""
    )


def downgrade() -> None:
    # Removing an enum value safely requires recreating the type
    op.execute(
        """
DO $$
BEGIN
    -- Rename existing type
    ALTER TYPE searchsourceconnectortype RENAME TO searchsourceconnectortype_old;

    -- Create new type without GITHUB_CONNECTOR
    CREATE TYPE searchsourceconnectortype AS ENUM(
        'SERPER_API', 
        'TAVILY_API', 
        'SLACK_CONNECTOR', 
        'NOTION_CONNECTOR'
    );

    -- Update table columns to use new type
    ALTER TABLE search_source_connectors
    ALTER COLUMN connector_type TYPE searchsourceconnectortype
    USING connector_type::text::searchsourceconnectortype;

    -- Drop old type
    DROP TYPE searchsourceconnectortype_old;
END$$;
"""
    )
