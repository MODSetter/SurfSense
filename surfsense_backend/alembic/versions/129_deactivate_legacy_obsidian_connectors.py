"""129_deactivate_legacy_obsidian_connectors

Revision ID: 129
Revises: 128
Create Date: 2026-04-18

Marks every pre-plugin OBSIDIAN_CONNECTOR row as legacy. We keep the
rows (and their indexed Documents) so existing search results don't
suddenly disappear, but we:

* set ``is_indexable = false`` and ``periodic_indexing_enabled = false``
  so the scheduler will never fire a server-side scan again,
* clear ``next_scheduled_at`` so the scheduler stops considering the
  row,
* merge ``{"legacy": true, "deactivated_at": "<now>"}`` into ``config``
  so the new ObsidianConfig view in the web UI can render the
  migration banner (and so a future cleanup script can find them).

A row is "pre-plugin" when its ``config`` does not already have
``source = "plugin"``. The new plugin indexer always writes
``config.source = "plugin"`` on first /obsidian/connect, so this
predicate is stable.
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


def downgrade() -> None:
    conn = op.get_bind()
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
