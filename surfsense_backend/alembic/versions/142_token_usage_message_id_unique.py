"""142_token_usage_message_id_unique

Revision ID: 142
Revises: 141
Create Date: 2026-05-04

Add a partial unique index on ``token_usage(message_id)`` where
``message_id IS NOT NULL``.

Why
---
Two writers can race on the same assistant turn's ``token_usage`` row:

  * ``finalize_assistant_turn`` (server-side, called from the streaming
    finally block in ``stream_new_chat`` / ``stream_resume_chat``)
  * ``append_message``'s recovery branch in
    ``app/routes/new_chat_routes.py`` (legacy frontend round-trip)

Both currently use ``SELECT ... THEN INSERT`` in separate sessions, so a
micro-second-aligned race could observe "no row" on each side and double
INSERT, producing duplicate ``token_usage`` rows for the same
``message_id``.

A partial unique index on ``message_id`` (``WHERE message_id IS NOT NULL``)
turns both writes into ``INSERT ... ON CONFLICT (message_id) DO NOTHING``
no-ops for the loser, hard-eliminating the race at the DB level. Partial
because non-chat usage rows (indexing, image generation, podcasts) keep
``message_id`` NULL — they're per-event, no de-dup needed.

Pre-flight
----------
Today's schema only has a non-unique index on ``message_id`` so a
duplicate population could already exist from any past race. We:

  * Detect duplicate ``message_id`` groups (``HAVING COUNT(*) > 1``).
  * If the group count is at or below ``DUPLICATE_ABORT_THRESHOLD`` (50)
    we dedupe by deleting all but the smallest ``id`` per group.
  * If the count exceeds the threshold we abort with a descriptive
    error rather than silently mutate prod data — operator must
    investigate before retrying.

Concurrency
-----------
``CREATE INDEX CONCURRENTLY`` is required on this hot table to avoid
stalling production writes during deploy (a regular ``CREATE INDEX``
holds an ACCESS EXCLUSIVE lock for the duration of the build, which
would block ``token_usage`` INSERTs for every active streaming chat).
The trade-off is a slower migration (CONCURRENTLY scans the table
twice) and the ``CREATE`` statement cannot run inside alembic's default
transaction wrapper — ``autocommit_block()`` handles that.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "142"
down_revision: str | None = "141"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


INDEX_NAME = "uq_token_usage_message_id"
TABLE_NAME = "token_usage"

# Refuse to silently mutate prod data if the duplicate population is
# unexpectedly large — operator should investigate the upstream cause
# before retrying. 50 is comfortably above any plausible duplicate
# count from the existing race window (the race is microseconds wide).
DUPLICATE_ABORT_THRESHOLD = 50


def upgrade() -> None:
    conn = op.get_bind()

    dup_groups = conn.execute(
        sa.text(
            "SELECT message_id, COUNT(*) AS n "
            "FROM token_usage "
            "WHERE message_id IS NOT NULL "
            "GROUP BY message_id "
            "HAVING COUNT(*) > 1"
        )
    ).fetchall()

    if len(dup_groups) > DUPLICATE_ABORT_THRESHOLD:
        raise RuntimeError(
            f"token_usage has {len(dup_groups)} duplicate message_id groups "
            f"(threshold={DUPLICATE_ABORT_THRESHOLD}). "
            "Resolve the duplicates manually before re-running this migration."
        )

    if dup_groups:
        # Delete all but the smallest-id row per duplicate group. The
        # smallest id is by definition the earliest insert, so we keep
        # the row most likely to reflect the actual stream's first
        # successful write.
        conn.execute(
            sa.text(
                """
                DELETE FROM token_usage
                WHERE id IN (
                    SELECT id FROM (
                        SELECT
                            id,
                            row_number() OVER (
                                PARTITION BY message_id ORDER BY id ASC
                            ) AS rn
                        FROM token_usage
                        WHERE message_id IS NOT NULL
                    ) ranked
                    WHERE rn > 1
                )
                """
            )
        )

    # CREATE INDEX CONCURRENTLY cannot run inside a transaction. Drop
    # alembic's auto-transaction for this op only.
    with op.get_context().autocommit_block():
        op.execute(
            f"CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS {INDEX_NAME} "
            f"ON {TABLE_NAME} (message_id) "
            "WHERE message_id IS NOT NULL"
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {INDEX_NAME}")
