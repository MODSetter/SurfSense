"""Add Composio connector types to SearchSourceConnectorType and DocumentType enums

Revision ID: 79
Revises: 78

This migration adds the Composio connector enum values to both:
- searchsourceconnectortype (for connector type tracking)
- documenttype (for document type tracking)

Composio is a managed OAuth integration service that allows connecting
to various third-party services (Google Drive, Gmail, Calendar, etc.)
without requiring separate OAuth app verification.

This migration adds three specific connector types:
- COMPOSIO_GOOGLE_DRIVE_CONNECTOR
- COMPOSIO_GMAIL_CONNECTOR
- COMPOSIO_GOOGLE_CALENDAR_CONNECTOR
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "79"
down_revision: str | None = "78"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Define the ENUM type names and the new values
CONNECTOR_ENUM = "searchsourceconnectortype"
CONNECTOR_NEW_VALUES = [
    "COMPOSIO_GOOGLE_DRIVE_CONNECTOR",
    "COMPOSIO_GMAIL_CONNECTOR",
    "COMPOSIO_GOOGLE_CALENDAR_CONNECTOR",
]
DOCUMENT_ENUM = "documenttype"
DOCUMENT_NEW_VALUES = [
    "COMPOSIO_GOOGLE_DRIVE_CONNECTOR",
    "COMPOSIO_GMAIL_CONNECTOR",
    "COMPOSIO_GOOGLE_CALENDAR_CONNECTOR",
]


def upgrade() -> None:
    """Upgrade schema - add Composio connector types to connector and document enums safely."""
    # Add each Composio connector type to searchsourceconnectortype only if not exists
    for value in CONNECTOR_NEW_VALUES:
        op.execute(
            f"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_enum e
                    JOIN pg_type t ON e.enumtypid = t.oid
                    WHERE t.typname = '{CONNECTOR_ENUM}' AND e.enumlabel = '{value}'
                ) THEN
                    ALTER TYPE {CONNECTOR_ENUM} ADD VALUE '{value}';
                END IF;
            END$$;
        """
        )

    # Add each Composio connector type to documenttype only if not exists
    for value in DOCUMENT_NEW_VALUES:
        op.execute(
            f"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_enum e
                    JOIN pg_type t ON e.enumtypid = t.oid
                    WHERE t.typname = '{DOCUMENT_ENUM}' AND e.enumlabel = '{value}'
                ) THEN
                    ALTER TYPE {DOCUMENT_ENUM} ADD VALUE '{value}';
                END IF;
            END$$;
        """
        )


def downgrade() -> None:
    """Downgrade schema - remove Composio connector types from connector and document enums.

    Note: PostgreSQL does not support removing enum values directly.
    To properly downgrade, you would need to:
    1. Delete any rows using the Composio connector type values
    2. Create new enums without the Composio connector types
    3. Alter the columns to use the new enums
    4. Drop the old enums

    This is left as a no-op since removing enum values is complex
    and typically not needed in practice.
    """
    pass
