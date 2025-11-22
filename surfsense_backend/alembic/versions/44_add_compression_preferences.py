"""add_compression_preferences

Revision ID: 44_add_compression_preferences
Revises: 43_add_is_public_to_searchspaces
Create Date: 2025-11-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '44_add_compression_preferences'
down_revision: Union[str, None] = '43_add_is_public_to_searchspaces'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add compression preference columns to user table."""
    # Add image compression level column (low, medium, high, none)
    op.add_column('user', sa.Column('image_compression_level', sa.String(20), nullable=False, server_default='medium'))

    # Add video compression level column (low, medium, high, none)
    op.add_column('user', sa.Column('video_compression_level', sa.String(20), nullable=False, server_default='medium'))

    # Add auto-compress enabled flag
    op.add_column('user', sa.Column('auto_compress_enabled', sa.Boolean(), nullable=False, server_default='true'))


def downgrade() -> None:
    """Remove compression preference columns from user table."""
    op.drop_column('user', 'auto_compress_enabled')
    op.drop_column('user', 'video_compression_level')
    op.drop_column('user', 'image_compression_level')
