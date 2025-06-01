"""Remove is_generated column from podcasts table

Revision ID: 7
Revises: 6

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7'
down_revision: Union[str, None] = '6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the is_generated column
    op.drop_column('podcasts', 'is_generated')


def downgrade() -> None:
    # Add back the is_generated column with its original constraints
    op.add_column('podcasts', sa.Column('is_generated', sa.Boolean(), nullable=False, server_default='false')) 