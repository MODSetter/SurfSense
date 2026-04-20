"""129_deactivate_legacy_obsidian_connectors

Revision ID: 129
Revises: 128
Create Date: 2026-04-18

Deactivates pre-plugin OBSIDIAN_CONNECTOR rows (keeping them and their
Documents, but flagging ``config.legacy = true`` and disabling scheduling)
and creates the partial unique index on
``(user_id, (config->>'vault_id'))`` for plugin-Obsidian rows that backs
the ``/obsidian/connect`` upsert.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "129"
down_revision: str | None = "128"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE search_source_connectors
            SET
                is_indexable = false,
                periodic_indexing_enabled = false,
                next_scheduled_at = NULL,
                config = COALESCE(config, '{}'::json)::jsonb
                         || jsonb_build_object(
                             'legacy', true,
                             'deactivated_at', to_char(
                                 now() AT TIME ZONE 'UTC',
                                 'YYYY-MM-DD"T"HH24:MI:SS"Z"'
                             )
                         )
            WHERE connector_type = 'OBSIDIAN_CONNECTOR'
              AND COALESCE((config::jsonb)->>'source', '') <> 'plugin'
            """
        )
    )

    conn.execute(
        sa.text(
            """
            CREATE UNIQUE INDEX search_source_connectors_obsidian_plugin_vault_uniq
            ON search_source_connectors (user_id, ((config->>'vault_id')))
            WHERE connector_type = 'OBSIDIAN_CONNECTOR'
              AND config->>'source' = 'plugin'
              AND config->>'vault_id' IS NOT NULL
            """
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "DROP INDEX IF EXISTS "
            "search_source_connectors_obsidian_plugin_vault_uniq"
        )
    )
    conn.execute(
        sa.text(
            """
            UPDATE search_source_connectors
            SET config = (config::jsonb - 'legacy' - 'deactivated_at')::json
            WHERE connector_type = 'OBSIDIAN_CONNECTOR'
              AND (config::jsonb) ? 'legacy'
            """
        )
    )
