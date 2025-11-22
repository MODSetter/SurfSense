"""add is_public field to searchspaces

Revision ID: 43
Revises: 42
Create Date: 2025-11-22

CRITICAL SECURITY: This migration adds the is_public field to enable space sharing functionality.
All existing spaces default to private (is_public=False) for security.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '43'
down_revision = '42'
branch_labels = None
depends_on = None


def upgrade():
    """Add is_public column with safe defaults"""
    # Add the column with server_default to avoid NULL issues on existing rows
    op.add_column('searchspaces',
        sa.Column('is_public', sa.Boolean(), nullable=False, server_default='false'))

    # Create index for query performance
    op.create_index('ix_searchspaces_is_public', 'searchspaces', ['is_public'])

    # Create composite index for common query pattern (user_id + is_public)
    op.create_index('ix_searchspaces_user_public', 'searchspaces', ['user_id', 'is_public'])


def downgrade():
    """Remove is_public column and indexes"""
    op.drop_index('ix_searchspaces_user_public', 'searchspaces')
    op.drop_index('ix_searchspaces_is_public', 'searchspaces')
    op.drop_column('searchspaces', 'is_public')
