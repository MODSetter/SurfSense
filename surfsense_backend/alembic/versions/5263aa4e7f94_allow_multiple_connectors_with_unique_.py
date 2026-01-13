"""allow_multiple_connectors_with_unique_names

Revision ID: 5263aa4e7f94
Revises: ffd7445eb90a
Create Date: 2026-01-13 12:23:31.481643

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5263aa4e7f94'
down_revision: Union[str, None] = 'ffd7445eb90a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Drop the old unique constraint
    op.drop_constraint(
        'uq_searchspace_user_connector_type',
        'search_source_connectors',
        type_='unique'
    )
    
    # Create new unique constraint that includes name
    op.create_unique_constraint(
        'uq_searchspace_user_connector_type_name',
        'search_source_connectors',
        ['search_space_id', 'user_id', 'connector_type', 'name']
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop the new constraint
    op.drop_constraint(
        'uq_searchspace_user_connector_type_name',
        'search_source_connectors',
        type_='unique'
    )
    
    # Restore the old constraint
    op.create_unique_constraint(
        'uq_searchspace_user_connector_type',
        'search_source_connectors',
        ['search_space_id', 'user_id', 'connector_type']
    )
