"""Add MCP connector type

Revision ID: 1053d0947cc1
Revises: 58
Create Date: 2026-01-09 15:19:51.827647

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1053d0947cc1'
down_revision: Union[str, None] = '58'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add MCP_CONNECTOR to SearchSourceConnectorType enum."""
    # Add new enum value using raw SQL
    op.execute(
        """
        ALTER TYPE searchsourceconnectortype ADD VALUE IF NOT EXISTS 'MCP_CONNECTOR';
        """
    )


def downgrade() -> None:
    """Remove MCP_CONNECTOR from SearchSourceConnectorType enum."""
    # Note: PostgreSQL does not support removing enum values directly.
    # To downgrade, you would need to:
    # 1. Create a new enum without MCP_CONNECTOR
    # 2. Alter the column to use the new enum
    # 3. Drop the old enum
    # This is left as a manual operation if needed.
    pass
