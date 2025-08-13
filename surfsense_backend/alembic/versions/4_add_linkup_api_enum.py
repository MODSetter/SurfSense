"""Add LINKUP_API to SearchSourceConnectorType enum

Revision ID: 4
Revises: 3
Create Date: 2025-08-13
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4"
down_revision: str | None = "3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add enum value only if it doesn't already exist.
    # Postgres will no-op with a NOTICE when the value is present.
    op.execute(
        "ALTER TYPE searchsourceconnectortype ADD VALUE IF NOT EXISTS 'LINKUP_API'"
    )


def downgrade() -> None:
    # To "remove" an enum value in Postgres, we must recreate the type
    # without that value, migrate the column, then drop the old type.
    op.execute(
        "ALTER TYPE searchsourceconnectortype RENAME TO searchsourceconnectortype_old"
    )
    op.execute(
        "CREATE TYPE searchsourceconnectortype AS ENUM("
        "'SERPER_API', 'TAVILY_API', 'SLACK_CONNECTOR', "
        "'NOTION_CONNECTOR', 'GITHUB_CONNECTOR', 'LINEAR_CONNECTOR'"
        ")"
    )
    op.execute(
        "ALTER TABLE search_source_connectors "
        "ALTER COLUMN connector_type "
        "TYPE searchsourceconnectortype "
        "USING connector_type::text::searchsourceconnectortype"
    )
    op.execute("DROP TYPE searchsourceconnectortype_old")
