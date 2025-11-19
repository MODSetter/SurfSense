"""add disable_registration to site_configuration

Revision ID: 39_add_disable_registration_to_site_configuration
Revises: 38_add_site_configuration_table
Create Date: 2025-11-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '39'
down_revision: Union[str, None] = '38'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add disable_registration column to site_configuration table
    op.add_column(
        'site_configuration',
        sa.Column('disable_registration', sa.Boolean(), nullable=False, server_default='false')
    )


def downgrade() -> None:
    # Remove disable_registration column
    op.drop_column('site_configuration', 'disable_registration')
