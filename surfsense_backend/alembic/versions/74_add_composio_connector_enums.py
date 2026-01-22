"""Add COMPOSIO_CONNECTOR to SearchSourceConnectorType and DocumentType enums

Revision ID: 74
Revises: 73
Create Date: 2026-01-21

This migration adds the COMPOSIO_CONNECTOR enum value to both:
- searchsourceconnectortype (for connector type tracking)
- documenttype (for document type tracking)

Composio is a managed OAuth integration service that allows connecting
to various third-party services (Google Drive, Gmail, Calendar, etc.)
without requiring separate OAuth app verification.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "74"
down_revision: str | None = "73"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Define the ENUM type names and the new value
CONNECTOR_ENUM = "searchsourceconnectortype"
CONNECTOR_NEW_VALUE = "COMPOSIO_CONNECTOR"
DOCUMENT_ENUM = "documenttype"
DOCUMENT_NEW_VALUE = "COMPOSIO_CONNECTOR"


def upgrade() -> None:
    """Upgrade schema - add COMPOSIO_CONNECTOR to connector and document enums safely."""
    # Add COMPOSIO_CONNECTOR to searchsourceconnectortype only if not exists
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

    # Add COMPOSIO_CONNECTOR to documenttype only if not exists
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
    """Downgrade schema - remove COMPOSIO_CONNECTOR from connector and document enums.
    
    Note: PostgreSQL does not support removing enum values directly.
    To properly downgrade, you would need to:
    1. Delete any rows using the COMPOSIO_CONNECTOR value
    2. Create new enums without COMPOSIO_CONNECTOR
    3. Alter the columns to use the new enums
    4. Drop the old enums
    
    This is left as a no-op since removing enum values is complex
    and typically not needed in practice.
    """
    pass
