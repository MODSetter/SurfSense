"""Let a connection be ElevenLabs' own, which does not speak OpenAI's API.

The only change is `auth_kind` accepting `elevenlabs`; its key is stored as any
connection's is.

SQLite cannot alter a CHECK, so the table is rebuilt from its own stored
definition with only the check changed. Dropping `provider_connections`
cascades through `selected_models.connection_id`, and foreign keys cannot be
switched off inside the migration's transaction, so every remote selection is
kept aside and put back.

Revision ID: 0033
Revises: 0032
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0033"
down_revision: str | Sequence[str] | None = "0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_WITHOUT = "CHECK (auth_kind IN ('api_key', 'chatgpt', 'claude_plan'))"
_WITH = "CHECK (auth_kind IN ('api_key', 'chatgpt', 'claude_plan', 'elevenlabs'))"


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
        raise RuntimeError("provider_connections is not the table 0033 expects")
    rebuilt = definition.replace(check_from, check_to).replace(
        head, 'CREATE TABLE "provider_connections_0033"', 1
    )

    op.execute(
        sa.text(
            "CREATE TEMP TABLE selections_0033 AS "
            "SELECT * FROM selected_models WHERE connection_id IS NOT NULL"
        )
    )
    op.execute(sa.text(rebuilt))
    op.execute(
        sa.text(
            "INSERT INTO provider_connections_0033 SELECT * FROM provider_connections"
        )
    )
    op.execute(sa.text("DROP TABLE provider_connections"))
    op.execute(
        sa.text("ALTER TABLE provider_connections_0033 RENAME TO provider_connections")
    )
    op.execute(sa.text("INSERT INTO selected_models SELECT * FROM selections_0033"))
    op.execute(sa.text("DROP TABLE selections_0033"))


def upgrade() -> None:
    _rebuild(_WITHOUT, _WITH)


def downgrade() -> None:
    # The old check cannot hold one; its selections go with it.
    op.execute(
        sa.text("DELETE FROM provider_connections WHERE auth_kind = 'elevenlabs'")
    )
    _rebuild(_WITH, _WITHOUT)
