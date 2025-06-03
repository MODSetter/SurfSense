"""Add DISCORD_CONNECTOR to SearchSourceConnectorType and DocumentType enums

Revision ID: 9
Revises: 8
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9"
down_revision: Union[str, None] = "8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Define the ENUM type name and the new value
CONNECTOR_ENUM = "searchsourceconnectortype"
CONNECTOR_NEW_VALUE = "DISCORD_CONNECTOR"
DOCUMENT_ENUM = "documenttype"
DOCUMENT_NEW_VALUE = "DISCORD_CONNECTOR"


def upgrade() -> None:
    """Upgrade schema - add DISCORD_CONNECTOR to connector and document enum."""
    # Add DISCORD_CONNECTOR to searchsourceconnectortype
    op.execute(f"ALTER TYPE {CONNECTOR_ENUM} ADD VALUE '{CONNECTOR_NEW_VALUE}'")
    # Add DISCORD_CONNECTOR to documenttype
    op.execute(f"ALTER TYPE {DOCUMENT_ENUM} ADD VALUE '{DOCUMENT_NEW_VALUE}'")


def downgrade() -> None:
    """Downgrade schema - remove DISCORD_CONNECTOR from connector and document enum."""

    # Old enum name
    old_connector_enum_name = f"{CONNECTOR_ENUM}_old"
    old_document_enum_name = f"{DOCUMENT_ENUM}_old"

    old_connector_values = (
        "SERPER_API",
        "TAVILY_API",
        "LINKUP_API",
        "SLACK_CONNECTOR",
        "NOTION_CONNECTOR",
        "GITHUB_CONNECTOR",
        "LINEAR_CONNECTOR",
    )
    old_document_values = (
        "EXTENSION",
        "CRAWLED_URL",
        "FILE",
        "SLACK_CONNECTOR",
        "NOTION_CONNECTOR",
        "YOUTUBE_VIDEO",
        "GITHUB_CONNECTOR",
        "LINEAR_CONNECTOR",
    )

    old_connector_values_sql = ", ".join([f"'{v}'" for v in old_connector_values])
    old_document_values_sql = ", ".join([f"'{v}'" for v in old_document_values])

    # Table and column names (adjust if different)
    connector_table_name = "search_source_connectors"
    connector_column_name = "connector_type"
    document_table_name = "documents"
    document_column_name = "document_type"

    # Connector Enum Downgrade Steps
    # 1. Rename the current connector enum type
    op.execute(f"ALTER TYPE {CONNECTOR_ENUM} RENAME TO {old_connector_enum_name}")

    # 2. Create the new connector enum type with the old values
    op.execute(f"CREATE TYPE {CONNECTOR_ENUM} AS ENUM({old_connector_values_sql})")

    # 3. Update the connector table:
    op.execute(
        f"ALTER TABLE {connector_table_name} "
        f"ALTER COLUMN {connector_column_name} "
        f"TYPE {CONNECTOR_ENUM} "
        f"USING {connector_column_name}::text::{CONNECTOR_ENUM}"
    )

    # 4. Drop the old connector enum type
    op.execute(f"DROP TYPE {old_connector_enum_name}")


    # Document Enum Downgrade Steps
    # 1. Rename the current document enum type
    op.execute(f"ALTER TYPE {DOCUMENT_ENUM} RENAME TO {old_document_enum_name}")

    # 2. Create the new document enum type with the old values
    op.execute(f"CREATE TYPE {DOCUMENT_ENUM} AS ENUM({old_document_values_sql})")

    # 3. Delete rows with the new value from the documents table
    op.execute(
        f"DELETE FROM {document_table_name} WHERE {document_column_name}::text = '{DOCUMENT_NEW_VALUE}'"
    )

    # 4. Alter the document table to use the new enum type (casting old values)
    op.execute(
        f"ALTER TABLE {document_table_name} "
        f"ALTER COLUMN {document_column_name} "
        f"TYPE {DOCUMENT_ENUM} "
        f"USING {document_column_name}::text::{DOCUMENT_ENUM}"
    )

    # 5. Drop the old enum types
    op.execute(f"DROP TYPE {old_document_enum_name}")

    # ### end Alembic commands ###
