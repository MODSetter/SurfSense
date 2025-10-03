"""add elasticsearch connector enum

Revision ID: 22
Revises: 21
Create Date: 2025-09-30 12:00:00.000000

"""
# import sqlalchemy as sa

from alembic import op

# revision identifiers
revision = "22_add_elasticsearch_connector_enums"
down_revision = "21_add_luma_connector_enums"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add ELASTICSEARCH to SearchSourceType enum
    op.execute("ALTER TYPE searchsourcetype ADD VALUE 'ELASTICSEARCH'")

    # Add ELASTICSEARCH to DocumentType enum
    op.execute("ALTER TYPE documenttype ADD VALUE 'ELASTICSEARCH'")


def downgrade() -> None:
    # Note: PostgreSQL doesn't support removing enum values
    # This would require recreating the enum types
    pass
