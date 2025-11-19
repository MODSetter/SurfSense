"""add site_configuration table

Revision ID: 38_add_site_configuration_table
Revises: 37_add_social_media_links_table
Create Date: 2025-11-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '38'
down_revision: Union[str, None] = '37'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create site_configuration table
    op.create_table(
        'site_configuration',
        sa.Column('id', sa.Integer(), nullable=False),

        # Header/Navbar toggles
        sa.Column('show_pricing_link', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('show_docs_link', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('show_github_link', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('show_sign_in', sa.Boolean(), nullable=False, server_default='true'),

        # Homepage toggles
        sa.Column('show_get_started_button', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('show_talk_to_us_button', sa.Boolean(), nullable=False, server_default='false'),

        # Footer toggles
        sa.Column('show_pages_section', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('show_legal_section', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('show_register_section', sa.Boolean(), nullable=False, server_default='false'),

        # Route disabling
        sa.Column('disable_pricing_route', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('disable_docs_route', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('disable_contact_route', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('disable_terms_route', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('disable_privacy_route', sa.Boolean(), nullable=False, server_default='true'),

        # Custom text
        sa.Column('custom_copyright', sa.String(length=200), nullable=True, server_default='SurfSense 2025'),

        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('id = 1', name='check_singleton')
    )

    # Create index
    op.create_index('ix_site_configuration_id', 'site_configuration', ['id'])

    # Insert default configuration (singleton pattern - only one row)
    op.execute("""
        INSERT INTO site_configuration (id) VALUES (1)
    """)


def downgrade() -> None:
    # Drop index
    op.drop_index('ix_site_configuration_id', table_name='site_configuration')

    # Drop table
    op.drop_table('site_configuration')
