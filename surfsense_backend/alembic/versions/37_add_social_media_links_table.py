"""add social_media_links table

Revision ID: 37_add_social_media_links_table
Revises: 36_remove_fk_constraints_for_global_llm_configs
Create Date: 2025-11-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '37'
down_revision: Union[str, None] = '36'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum type
    social_media_platform_enum = sa.Enum(
        'MASTODON', 'PIXELFED', 'BOOKWYRM', 'LEMMY', 'PEERTUBE',
        'GITHUB', 'GITLAB', 'MATRIX', 'LINKEDIN', 'WEBSITE', 'EMAIL', 'OTHER',
        name='socialmediaplatform'
    )
    social_media_platform_enum.create(op.get_bind(), checkfirst=True)

    # Create social_media_links table
    op.create_table(
        'social_media_links',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('platform', social_media_platform_enum, nullable=False),
        sa.Column('url', sa.String(length=500), nullable=False),
        sa.Column('label', sa.String(length=100), nullable=True),
        sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes
    op.create_index('ix_social_media_links_id', 'social_media_links', ['id'])
    op.create_index('ix_social_media_links_platform', 'social_media_links', ['platform'])
    op.create_index('ix_social_media_links_created_at', 'social_media_links', ['created_at'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_social_media_links_created_at', table_name='social_media_links')
    op.drop_index('ix_social_media_links_platform', table_name='social_media_links')
    op.drop_index('ix_social_media_links_id', table_name='social_media_links')

    # Drop table
    op.drop_table('social_media_links')

    # Drop enum type
    sa.Enum(name='socialmediaplatform').drop(op.get_bind(), checkfirst=True)
