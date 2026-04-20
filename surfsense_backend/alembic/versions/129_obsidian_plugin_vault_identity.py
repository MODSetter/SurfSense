"""129_obsidian_plugin_vault_identity

Revision ID: 129
Revises: 128
Create Date: 2026-04-21

Locks down vault identity for the Obsidian plugin connector:

- Deactivates pre-plugin OBSIDIAN_CONNECTOR rows.
- Partial unique index on ``(user_id, (config->>'vault_id'))`` for the
  ``/obsidian/connect`` upsert fast path.
- Partial unique index on ``(user_id, (config->>'vault_fingerprint'))``
  so two devices observing the same vault content can never produce
  two connector rows. Collisions are caught by the route handler and
  routed through the merge path.
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
            CREATE UNIQUE INDEX IF NOT EXISTS
                search_source_connectors_obsidian_plugin_vault_uniq
            ON search_source_connectors (user_id, ((config->>'vault_id')))
            WHERE connector_type = 'OBSIDIAN_CONNECTOR'
              AND config->>'source' = 'plugin'
              AND config->>'vault_id' IS NOT NULL
            """
        )
    )

    conn.execute(
        sa.text(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS
                search_source_connectors_obsidian_plugin_fingerprint_uniq
            ON search_source_connectors (user_id, ((config->>'vault_fingerprint')))
            WHERE connector_type = 'OBSIDIAN_CONNECTOR'
              AND config->>'source' = 'plugin'
              AND config->>'vault_fingerprint' IS NOT NULL
            """
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "DROP INDEX IF EXISTS "
            "search_source_connectors_obsidian_plugin_fingerprint_uniq"
        )
    )
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
