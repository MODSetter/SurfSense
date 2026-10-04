"""Let a connection sign in with a ChatGPT account instead of a key.

Every existing connection signs in with its key, so `auth_kind` defaults to
`api_key` and nothing is backfilled.

Columns are added by plain ALTER TABLE, never batch mode: a batch rebuild drops
`provider_connections`, and with foreign keys on that cascades through
`selected_models.connection_id` and deletes every remote selection.

Revision ID: 0023
Revises: 0022
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0023"
down_revision: str | Sequence[str] | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COLUMNS = ("auth_kind", "oauth_ciphertext", "token_version")


def upgrade() -> None:
    # Raw, because op.add_column drops a column-level CHECK on SQLite.
    op.execute(
        sa.text(
            "ALTER TABLE provider_connections ADD COLUMN auth_kind VARCHAR "
            "DEFAULT 'api_key' NOT NULL "
            "CONSTRAINT ck_provider_connections_auth_kind "
            "CHECK (auth_kind IN ('api_key', 'chatgpt'))"
        )
    )
    op.execute(
        sa.text("ALTER TABLE provider_connections ADD COLUMN oauth_ciphertext BLOB")
    )
    op.execute(
        sa.text(
            "ALTER TABLE provider_connections ADD COLUMN token_version INTEGER "
            "DEFAULT '0' NOT NULL"
        )
    )


def downgrade() -> None:
    # The old schema has no way to sign in but a key.
    op.execute(sa.text("DELETE FROM provider_connections WHERE auth_kind <> 'api_key'"))
    for column in reversed(COLUMNS):
        op.execute(sa.text(f"ALTER TABLE provider_connections DROP COLUMN {column}"))
