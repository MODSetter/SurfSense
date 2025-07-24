"""Remove is_generated column from podcasts table

Revision ID: 7
Revises: 6

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '7'
down_revision: str | None = '6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Drop the is_generated column
    op.drop_column('podcasts', 'is_generated')


def downgrade() -> None:
    # Add back the is_generated column with its original constraints
    op.add_column('podcasts', sa.Column('is_generated', sa.Boolean(), nullable=False, server_default='false')) 