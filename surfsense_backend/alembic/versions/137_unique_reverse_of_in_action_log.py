"""137_unique_reverse_of_in_action_log

Revision ID: 137
Revises: 136
Create Date: 2026-04-29

Protect ``agent_action_log.reverse_of`` against double inserts. Two
concurrent revert calls (single-action route + the per-turn batch
route, or two batch routes racing) both pass the
``_was_already_reverted`` SELECT and both insert their own
``_revert:*`` rows. The application-level idempotency check is racy
because there's no DB constraint backing it.

This migration adds a partial unique index on ``reverse_of`` (PostgreSQL
``WHERE reverse_of IS NOT NULL``) so the second concurrent insert raises
``IntegrityError`` and the route can translate it to ``"already_reverted"``
deterministically.

The plain ``UniqueConstraint`` flavour can't be used because most
existing rows have ``reverse_of = NULL`` (only revert rows fill it),
and Postgres does treat NULL as distinct in unique indexes — but a
partial index is the cleanest expression of intent and works even on
older Postgres releases that distinguish NULL handling.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "137"
down_revision: str | None = "136"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_INDEX_NAME = "ux_agent_action_log_reverse_of"


def upgrade() -> None:
    # Defensively de-dup any pre-existing double-revert rows before
    # adding the unique index. Keeps the OLDEST row (smallest id) and
    # NULLs out the duplicates' ``reverse_of`` so they survive as audit
    # trail but no longer claim to be the canonical revert. We do NOT
    # delete them — operators can still inspect them via /actions.
    op.execute(
        """
        WITH dups AS (
            SELECT id,
                   reverse_of,
                   ROW_NUMBER() OVER (
                       PARTITION BY reverse_of ORDER BY id ASC
                   ) AS rn
              FROM agent_action_log
             WHERE reverse_of IS NOT NULL
        )
        UPDATE agent_action_log
           SET reverse_of = NULL
         WHERE id IN (SELECT id FROM dups WHERE rn > 1)
        """
    )

    op.create_index(
        _INDEX_NAME,
        "agent_action_log",
        ["reverse_of"],
        unique=True,
        postgresql_where="reverse_of IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_index(_INDEX_NAME, table_name="agent_action_log")
