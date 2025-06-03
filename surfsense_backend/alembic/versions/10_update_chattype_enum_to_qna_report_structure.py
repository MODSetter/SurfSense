"""Update ChatType enum from GENERAL/DEEP/DEEPER/DEEPEST to QNA/REPORT_* structure

Revision ID: 10
Revises: 9
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "10"
down_revision: Union[str, None] = "9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Define the ENUM type name
CHAT_TYPE_ENUM = "chattype"


def upgrade() -> None:
    """Upgrade schema - replace ChatType enum values with new QNA/REPORT structure."""
    
    # Old enum name for temporary storage
    old_enum_name = f"{CHAT_TYPE_ENUM}_old"
    
    # New enum values
    new_values = (
        "QNA",
        "REPORT_GENERAL", 
        "REPORT_DEEP",
        "REPORT_DEEPER"
    )
    new_values_sql = ", ".join([f"'{v}'" for v in new_values])
    
    # Table and column info
    table_name = "chats"
    column_name = "type"
    
    # Step 1: Rename the current enum type
    op.execute(f"ALTER TYPE {CHAT_TYPE_ENUM} RENAME TO {old_enum_name}")
    
    # Step 2: Create the new enum type with new values
    op.execute(f"CREATE TYPE {CHAT_TYPE_ENUM} AS ENUM({new_values_sql})")
    
    # Step 3: Add a temporary column with the new type
    op.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name}_new {CHAT_TYPE_ENUM}")
    
    # Step 4: Update the temporary column with mapped values
    op.execute(f"UPDATE {table_name} SET {column_name}_new = 'QNA' WHERE {column_name}::text = 'GENERAL'")
    op.execute(f"UPDATE {table_name} SET {column_name}_new = 'REPORT_DEEP' WHERE {column_name}::text = 'DEEP'")
    op.execute(f"UPDATE {table_name} SET {column_name}_new = 'REPORT_DEEPER' WHERE {column_name}::text = 'DEEPER'")
    op.execute(f"UPDATE {table_name} SET {column_name}_new = 'REPORT_DEEPER' WHERE {column_name}::text = 'DEEPEST'")
    
    # Step 5: Drop the old column
    op.execute(f"ALTER TABLE {table_name} DROP COLUMN {column_name}")
    
    # Step 6: Rename the new column to the original name
    op.execute(f"ALTER TABLE {table_name} RENAME COLUMN {column_name}_new TO {column_name}")
    
    # Step 7: Drop the old enum type
    op.execute(f"DROP TYPE {old_enum_name}")


def downgrade() -> None:
    """Downgrade schema - revert ChatType enum to old GENERAL/DEEP/DEEPER/DEEPEST structure."""
    
    # Old enum name for temporary storage
    old_enum_name = f"{CHAT_TYPE_ENUM}_old"
    
    # Original enum values
    original_values = (
        "GENERAL",
        "DEEP", 
        "DEEPER",
        "DEEPEST"
    )
    original_values_sql = ", ".join([f"'{v}'" for v in original_values])
    
    # Table and column info
    table_name = "chats"
    column_name = "type"
    
    # Step 1: Rename the current enum type
    op.execute(f"ALTER TYPE {CHAT_TYPE_ENUM} RENAME TO {old_enum_name}")
    
    # Step 2: Create the new enum type with original values
    op.execute(f"CREATE TYPE {CHAT_TYPE_ENUM} AS ENUM({original_values_sql})")
    
    # Step 3: Add a temporary column with the original type
    op.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name}_new {CHAT_TYPE_ENUM}")
    
    # Step 4: Update the temporary column with mapped values back to old values
    op.execute(f"UPDATE {table_name} SET {column_name}_new = 'GENERAL' WHERE {column_name}::text = 'QNA'")
    op.execute(f"UPDATE {table_name} SET {column_name}_new = 'GENERAL' WHERE {column_name}::text = 'REPORT_GENERAL'")
    op.execute(f"UPDATE {table_name} SET {column_name}_new = 'DEEP' WHERE {column_name}::text = 'REPORT_DEEP'")
    op.execute(f"UPDATE {table_name} SET {column_name}_new = 'DEEPER' WHERE {column_name}::text = 'REPORT_DEEPER'")
    
    # Step 5: Drop the old column
    op.execute(f"ALTER TABLE {table_name} DROP COLUMN {column_name}")
    
    # Step 6: Rename the new column to the original name
    op.execute(f"ALTER TABLE {table_name} RENAME COLUMN {column_name}_new TO {column_name}")
    
    # Step 7: Drop the old enum type
    op.execute(f"DROP TYPE {old_enum_name}") 