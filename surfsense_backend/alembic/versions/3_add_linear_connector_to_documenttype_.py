"""Add LINEAR_CONNECTOR to DocumentType enum

Revision ID: 3
Revises: 2

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3'
down_revision: Union[str, None] = '2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Define the ENUM type name and the new value
ENUM_NAME = 'documenttype' # Make sure this matches the name in your DB (usually lowercase class name)
NEW_VALUE = 'LINEAR_CONNECTOR'

def upgrade() -> None:
    """Upgrade schema."""
    op.execute(f"ALTER TYPE {ENUM_NAME} ADD VALUE '{NEW_VALUE}'")
        

# Warning: This will delete all rows with the new value
def downgrade() -> None:
    """Downgrade schema - remove LINEAR_CONNECTOR from enum."""

    # The old type name
    old_enum_name = f"{ENUM_NAME}_old"

    # Enum values *before* LINEAR_CONNECTOR was added
    old_values = (
        'EXTENSION',
        'CRAWLED_URL',
        'FILE',
        'SLACK_CONNECTOR',
        'NOTION_CONNECTOR',
        'YOUTUBE_VIDEO',
        'GITHUB_CONNECTOR'
    )
    old_values_sql = ", ".join([f"'{v}'" for v in old_values])

    # Table and column names (adjust if different)
    table_name = 'documents'
    column_name = 'document_type'

    # 1. Rename the current enum type
    op.execute(f"ALTER TYPE {ENUM_NAME} RENAME TO {old_enum_name}")

    # 2. Create the new enum type with the old values
    op.execute(f"CREATE TYPE {ENUM_NAME} AS ENUM({old_values_sql})")

    # 3. Update the table: 
    op.execute(
        f"DELETE FROM {table_name} WHERE {column_name}::text = '{NEW_VALUE}'"
    )

    # 4. Alter the column to use the new enum type (casting old values)
    op.execute(
        f"ALTER TABLE {table_name} ALTER COLUMN {column_name} "
        f"TYPE {ENUM_NAME} USING {column_name}::text::{ENUM_NAME}"
    )

    # 5. Drop the old enum type
    op.execute(f"DROP TYPE {old_enum_name}")
    # ### end Alembic commands ### 