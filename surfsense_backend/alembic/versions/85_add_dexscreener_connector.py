"""add dexscreener connector enum

Revision ID: 85_add_dexscreener_connector
Revises: 84_migrate_global_llm_configs_to_auto_mode
Create Date: 2026-01-31 17:14:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '85'
down_revision = '84'
branch_labels = None
depends_on = None


def upgrade():
    """Add DEXSCREENER_CONNECTOR to searchsourceconnectortype and documenttype enums."""
    # Add new enum value using raw SQL
    # Note: ALTER TYPE ... ADD VALUE cannot be executed inside a transaction block
    # Alembic handles this automatically when using op.execute()
    op.execute(
        "ALTER TYPE searchsourceconnectortype ADD VALUE IF NOT EXISTS 'DEXSCREENER_CONNECTOR'"
    )
    op.execute(
        "ALTER TYPE documenttype ADD VALUE IF NOT EXISTS 'DEXSCREENER_CONNECTOR'"
    )


def downgrade():
    """
    Downgrade is not supported for enum value removal in PostgreSQL.
    
    Removing enum values requires:
    1. Removing all references to the value
    2. Creating a new enum type without the value
    3. Migrating all columns to use the new type
    4. Dropping the old type
    
    This is complex and risky, so we don't support automatic downgrade.
    If you need to remove this enum value, do it manually.
    """
    pass
