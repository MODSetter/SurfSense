"""Remove char limit on title columns

Revision ID: 5
Revises: 4

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5'
down_revision: Union[str, None] = '4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Alter Chat table
    op.alter_column('chats', 'title',
                    existing_type=sa.String(200),
                    type_=sa.String(),
                    existing_nullable=False)
    
    # Alter Document table
    op.alter_column('documents', 'title',
                    existing_type=sa.String(200),
                    type_=sa.String(),
                    existing_nullable=False)
    
    # Alter Podcast table
    op.alter_column('podcasts', 'title',
                    existing_type=sa.String(200),
                    type_=sa.String(),
                    existing_nullable=False)


def downgrade() -> None:
    # Revert Chat table
    op.alter_column('chats', 'title',
                    existing_type=sa.String(),
                    type_=sa.String(200),
                    existing_nullable=False)
    
    # Revert Document table
    op.alter_column('documents', 'title',
                    existing_type=sa.String(),
                    type_=sa.String(200),
                    existing_nullable=False)
    
    # Revert Podcast table
    op.alter_column('podcasts', 'title',
                    existing_type=sa.String(),
                    type_=sa.String(200),
                    existing_nullable=False) 