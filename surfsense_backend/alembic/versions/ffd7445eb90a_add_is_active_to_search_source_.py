"""add_is_active_to_search_source_connectors

Revision ID: ffd7445eb90a
Revises: 60
Create Date: 2026-01-12 22:11:26.132654

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ffd7445eb90a'
down_revision: Union[str, None] = '60'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add is_active column to search_source_connectors table
    op.add_column(
        'search_source_connectors',
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true())
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Remove is_active column from search_source_connectors table
    op.drop_column('search_source_connectors', 'is_active')
