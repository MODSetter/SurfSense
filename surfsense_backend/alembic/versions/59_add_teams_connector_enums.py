"""Add TEAMS_CONNECTOR to SearchSourceConnectorType and DocumentType enums

Revision ID: 59
Revises: 58
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "59"
down_revision: str | None = "58"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Define the ENUM type name and the new value
CONNECTOR_ENUM = "searchsourceconnectortype"
CONNECTOR_NEW_VALUE = "TEAMS_CONNECTOR"
DOCUMENT_ENUM = "documenttype"
DOCUMENT_NEW_VALUE = "TEAMS_CONNECTOR"


def upgrade() -> None:
    """Upgrade schema - add TEAMS_CONNECTOR to connector and document enum safely."""
    # Add TEAMS_CONNECTOR to searchsourceconnectortype only if not exists
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_enum
                WHERE enumlabel = '{CONNECTOR_NEW_VALUE}'
                AND enumtypid = (SELECT oid FROM pg_type WHERE typname = '{CONNECTOR_ENUM}')
            ) THEN
                ALTER TYPE {CONNECTOR_ENUM} ADD VALUE '{CONNECTOR_NEW_VALUE}';
            END IF;
        END$$;
    """
    )

    # Add TEAMS_CONNECTOR to documenttype only if not exists
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_enum
                WHERE enumlabel = '{DOCUMENT_NEW_VALUE}'
                AND enumtypid = (SELECT oid FROM pg_type WHERE typname = '{DOCUMENT_ENUM}')
            ) THEN
                ALTER TYPE {DOCUMENT_ENUM} ADD VALUE '{DOCUMENT_NEW_VALUE}';
            END IF;
        END$$;
    """
    )


def downgrade() -> None:
    """Downgrade schema - remove TEAMS_CONNECTOR from connector and document enum."""

    # Old enum name
    old_connector_enum_name = f"{CONNECTOR_ENUM}_old"
    old_document_enum_name = f"{DOCUMENT_ENUM}_old"

    # All connector values except TEAMS_CONNECTOR
    old_connector_values = (
        "SERPER_API",
        "TAVILY_API",
        "SEARXNG_API",
        "LINKUP_API",
        "BAIDU_SEARCH_API",
        "SLACK_CONNECTOR",
        "NOTION_CONNECTOR",
        "GITHUB_CONNECTOR",
        "LINEAR_CONNECTOR",
        "DISCORD_CONNECTOR",
        "JIRA_CONNECTOR",
        "CONFLUENCE_CONNECTOR",
        "CLICKUP_CONNECTOR",
        "GOOGLE_CALENDAR_CONNECTOR",
        "GOOGLE_GMAIL_CONNECTOR",
        "GOOGLE_DRIVE_CONNECTOR",
        "AIRTABLE_CONNECTOR",
        "LUMA_CONNECTOR",
        "ELASTICSEARCH_CONNECTOR",
        "WEBCRAWLER_CONNECTOR",
    )

    # All document values except TEAMS_CONNECTOR
    old_document_values = (
        "EXTENSION",
        "CRAWLED_URL",
        "FILE",
        "SLACK_CONNECTOR",
        "NOTION_CONNECTOR",
        "YOUTUBE_VIDEO",
        "GITHUB_CONNECTOR",
        "LINEAR_CONNECTOR",
        "DISCORD_CONNECTOR",
        "JIRA_CONNECTOR",
        "CONFLUENCE_CONNECTOR",
        "CLICKUP_CONNECTOR",
        "GOOGLE_CALENDAR_CONNECTOR",
        "GOOGLE_GMAIL_CONNECTOR",
        "GOOGLE_DRIVE_FILE",
        "AIRTABLE_CONNECTOR",
        "LUMA_CONNECTOR",
        "ELASTICSEARCH_CONNECTOR",
        "BOOKSTACK_CONNECTOR",
        "CIRCLEBACK",
        "NOTE",
    )

    old_connector_values_sql = ", ".join([f"'{v}'" for v in old_connector_values])
    old_document_values_sql = ", ".join([f"'{v}'" for v in old_document_values])

    # Table and column names
    connector_table_name = "search_source_connectors"
    connector_column_name = "connector_type"
    document_table_name = "documents"
    document_column_name = "document_type"

    # Connector Enum Downgrade Steps
    # 1. Rename the current connector enum type
    op.execute(f"ALTER TYPE {CONNECTOR_ENUM} RENAME TO {old_connector_enum_name}")

    # 2. Create the new connector enum type with the old values
    op.execute(f"CREATE TYPE {CONNECTOR_ENUM} AS ENUM({old_connector_values_sql})")

    # 3. Alter the column to use the new connector enum type
    op.execute(
        f"""
        ALTER TABLE {connector_table_name}
        ALTER COLUMN {connector_column_name} TYPE {CONNECTOR_ENUM}
        USING {connector_column_name}::text::{CONNECTOR_ENUM}
    """
    )

    # 4. Drop the old connector enum type
    op.execute(f"DROP TYPE {old_connector_enum_name}")

    # Document Enum Downgrade Steps
    # 1. Rename the current document enum type
    op.execute(f"ALTER TYPE {DOCUMENT_ENUM} RENAME TO {old_document_enum_name}")

    # 2. Create the new document enum type with the old values
    op.execute(f"CREATE TYPE {DOCUMENT_ENUM} AS ENUM({old_document_values_sql})")

    # 3. Alter the column to use the new document enum type
    op.execute(
        f"""
        ALTER TABLE {document_table_name}
        ALTER COLUMN {document_column_name} TYPE {DOCUMENT_ENUM}
        USING {document_column_name}::text::{DOCUMENT_ENUM}
    """
    )

    # 4. Drop the old document enum type
    op.execute(f"DROP TYPE {old_document_enum_name}")
