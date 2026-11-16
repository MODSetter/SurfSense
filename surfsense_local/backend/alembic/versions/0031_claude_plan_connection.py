"""Let a connection be a Claude plan, run through the user's own Claude Code.

The only change is `auth_kind` accepting `claude_plan`. A Claude plan stores no
credential, and what Claude Code reports about itself is read live, so no
column is added.

SQLite cannot alter a CHECK, so the table is rebuilt from its own stored
definition with only the check changed. Dropping `provider_connections`
cascades through `selected_models.connection_id`, and foreign keys cannot be
switched off inside the migration's transaction, so every remote selection is
kept aside and put back.

Revision ID: 0031
Revises: 0030
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0031"
down_revision: str | Sequence[str] | None = "0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_WITHOUT = "CHECK (auth_kind IN ('api_key', 'chatgpt'))"
_WITH = "CHECK (auth_kind IN ('api_key', 'chatgpt', 'claude_plan'))"


def _rebuild(check_from: str, check_to: str) -> None:
    connection = op.get_bind()
    definition = connection.execute(
        sa.text(
            "SELECT sql FROM sqlite_master "
            "WHERE type = 'table' AND name = 'provider_connections'"
        )
    ).scalar_one()
    head = 'CREATE TABLE "provider_connections"'
    if definition.count(check_from) != 1 or not definition.startswith(head):
        raise RuntimeError("provider_connections is not the table 0031 expects")
    rebuilt = definition.replace(check_from, check_to).replace(
        head, 'CREATE TABLE "provider_connections_0031"', 1
    )

    op.execute(
        sa.text(
            "CREATE TEMP TABLE selections_0031 AS "
            "SELECT * FROM selected_models WHERE connection_id IS NOT NULL"
        )
    )
    op.execute(sa.text(rebuilt))
    op.execute(
        sa.text(
            "INSERT INTO provider_connections_0031 SELECT * FROM provider_connections"
        )
    )
    op.execute(sa.text("DROP TABLE provider_connections"))
    op.execute(
        sa.text("ALTER TABLE provider_connections_0031 RENAME TO provider_connections")
    )
    op.execute(sa.text("INSERT INTO selected_models SELECT * FROM selections_0031"))
    op.execute(sa.text("DROP TABLE selections_0031"))


def upgrade() -> None:
    _rebuild(_WITHOUT, _WITH)


def downgrade() -> None:
    # The old check cannot hold a Claude plan; its selections go with it.
    op.execute(
        sa.text("DELETE FROM provider_connections WHERE auth_kind = 'claude_plan'")
    )
    _rebuild(_WITH, _WITHOUT)
