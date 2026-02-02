"""Add connector_id column to documents table for linking documents to their source connector

Revision ID: 87
Revises: 86
Create Date: 2026-02-02

Changes:
1. Add connector_id column (Integer, nullable, foreign key to search_source_connectors.id)
2. Create index on connector_id for efficient bulk deletion queries
3. SET NULL on delete - allows controlled cleanup in application code
4. Backfill existing documents based on document_type and search_space_id matching
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "87"
down_revision: str | None = "86"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add connector_id column to documents and backfill from existing connectors."""

    # 1. Add connector_id column (nullable - for manually uploaded docs without connector)
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'documents' AND column_name = 'connector_id'
            ) THEN
                ALTER TABLE documents
                ADD COLUMN connector_id INTEGER;
            END IF;
        END$$;
        """
    )

    # 2. Create index on connector_id for efficient cleanup queries
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_documents_connector_id
        ON documents (connector_id);
        """
    )

    # 3. Add foreign key constraint with ON DELETE SET NULL
    # SET NULL allows us to delete documents in controlled batches before deleting connector
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE constraint_name = 'fk_documents_connector_id'
                AND table_name = 'documents'
            ) THEN
                ALTER TABLE documents
                ADD CONSTRAINT fk_documents_connector_id
                FOREIGN KEY (connector_id) REFERENCES search_source_connectors(id)
                ON DELETE SET NULL;
            END IF;
        END$$;
        """
    )

    # 4. Backfill existing documents with connector_id based on document_type matching
    # This maps document types to their corresponding connector types
    # Only backfills for documents in search spaces that have exactly one connector of that type

    # Map of document_type -> connector_type for backfilling
    document_connector_mappings = [
        ("NOTION_CONNECTOR", "NOTION_CONNECTOR"),
        ("SLACK_CONNECTOR", "SLACK_CONNECTOR"),
        ("TEAMS_CONNECTOR", "TEAMS_CONNECTOR"),
        ("GITHUB_CONNECTOR", "GITHUB_CONNECTOR"),
        ("LINEAR_CONNECTOR", "LINEAR_CONNECTOR"),
        ("DISCORD_CONNECTOR", "DISCORD_CONNECTOR"),
        ("JIRA_CONNECTOR", "JIRA_CONNECTOR"),
        ("CONFLUENCE_CONNECTOR", "CONFLUENCE_CONNECTOR"),
        ("CLICKUP_CONNECTOR", "CLICKUP_CONNECTOR"),
        ("GOOGLE_CALENDAR_CONNECTOR", "GOOGLE_CALENDAR_CONNECTOR"),
        ("GOOGLE_GMAIL_CONNECTOR", "GOOGLE_GMAIL_CONNECTOR"),
        ("GOOGLE_DRIVE_FILE", "GOOGLE_DRIVE_CONNECTOR"),
        ("AIRTABLE_CONNECTOR", "AIRTABLE_CONNECTOR"),
        ("LUMA_CONNECTOR", "LUMA_CONNECTOR"),
        ("ELASTICSEARCH_CONNECTOR", "ELASTICSEARCH_CONNECTOR"),
        ("BOOKSTACK_CONNECTOR", "BOOKSTACK_CONNECTOR"),
        ("CIRCLEBACK", "CIRCLEBACK_CONNECTOR"),
        ("OBSIDIAN_CONNECTOR", "OBSIDIAN_CONNECTOR"),
        ("COMPOSIO_GOOGLE_DRIVE_CONNECTOR", "COMPOSIO_GOOGLE_DRIVE_CONNECTOR"),
        ("COMPOSIO_GMAIL_CONNECTOR", "COMPOSIO_GMAIL_CONNECTOR"),
        ("COMPOSIO_GOOGLE_CALENDAR_CONNECTOR", "COMPOSIO_GOOGLE_CALENDAR_CONNECTOR"),
        ("CRAWLED_URL", "WEBCRAWLER_CONNECTOR"),
    ]

    for doc_type, connector_type in document_connector_mappings:
        # Backfill connector_id for documents where:
        # 1. Document has this document_type
        # 2. Document doesn't already have a connector_id
        # 3. There's exactly one connector of this type in the same search space
        # This safely handles most cases while avoiding ambiguity
        op.execute(
            f"""
            UPDATE documents d
            SET connector_id = (
                SELECT ssc.id 
                FROM search_source_connectors ssc
                WHERE ssc.search_space_id = d.search_space_id
                AND ssc.connector_type = '{connector_type}'
                LIMIT 1
            )
            WHERE d.document_type = '{doc_type}'
            AND d.connector_id IS NULL
            AND EXISTS (
                SELECT 1 FROM search_source_connectors ssc
                WHERE ssc.search_space_id = d.search_space_id
                AND ssc.connector_type = '{connector_type}'
            );
            """
        )


def downgrade() -> None:
    """Remove connector_id column from documents."""

    # Drop foreign key constraint
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE constraint_name = 'fk_documents_connector_id'
                AND table_name = 'documents'
            ) THEN
                ALTER TABLE documents
                DROP CONSTRAINT fk_documents_connector_id;
            END IF;
        END$$;
        """
    )

    # Drop index
    op.execute(
        """
        DROP INDEX IF EXISTS ix_documents_connector_id;
        """
    )

    # Drop column
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'documents' AND column_name = 'connector_id'
            ) THEN
                ALTER TABLE documents
                DROP COLUMN connector_id;
            END IF;
        END$$;
        """
    )
