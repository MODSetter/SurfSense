from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e55302644c51"
down_revision: str | None = "1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Define the ENUM type name and the new value
ENUM_NAME = "documenttype"
NEW_VALUE = "GITHUB_CONNECTOR"


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        f"""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_enum
            WHERE enumlabel = '{NEW_VALUE}'
            AND enumtypid = (
                SELECT oid FROM pg_type WHERE typname = '{ENUM_NAME}'
            )
        ) THEN
            ALTER TYPE {ENUM_NAME} ADD VALUE '{NEW_VALUE}';
        END IF;
    END$$;
    """
    )


def downgrade() -> None:
    """Downgrade schema - remove GITHUB_CONNECTOR from enum."""
    old_enum_name = f"{ENUM_NAME}_old"

    old_values = (
        "EXTENSION",
        "CRAWLED_URL",
        "FILE",
        "SLACK_CONNECTOR",
        "NOTION_CONNECTOR",
        "YOUTUBE_VIDEO",
    )
    old_values_sql = ", ".join([f"'{v}'" for v in old_values])

    table_name = "documents"
    column_name = "document_type"

    # 1. Create the new enum type with the old values
    op.execute(f"CREATE TYPE {old_enum_name} AS ENUM({old_values_sql})")

    # 2. Delete rows using the new value
    op.execute(f"DELETE FROM {table_name} WHERE {column_name}::text = '{NEW_VALUE}'")

    # 3. Alter the column to use the old enum type
    op.execute(
        f"ALTER TABLE {table_name} ALTER COLUMN {column_name} "
        f"TYPE {old_enum_name} USING {column_name}::text::{old_enum_name}"
    )

    # 4. Drop the current enum type and rename the old one
    op.execute(f"DROP TYPE {ENUM_NAME}")
    op.execute(f"ALTER TYPE {old_enum_name} RENAME TO {ENUM_NAME}")
