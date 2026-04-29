"""135_action_log_correlation_ids

Revision ID: 135
Revises: 134
Create Date: 2026-04-29

Action-log correlation-id cleanup.

Background
----------
``agent_action_log.turn_id`` is misnamed. ``ActionLogMiddleware`` writes
the LangChain ``tool_call.id`` into that column today (see
``action_log.py:_resolve_turn_id``), and ``kb_persistence._find_action_ids_batch``
joins on it as such. The real chat-turn id (``f"{chat_id}:{ms}"`` from
``stream_new_chat.py``) lives in ``config.configurable.turn_id`` and was
never persisted.

This migration introduces two new, correctly-named columns:

* ``tool_call_id`` (LangChain tool-call id, what ``turn_id`` actually held)
* ``chat_turn_id`` (the per-turn correlation id from
  ``configurable.turn_id`` — used by the per-turn ``revert-turn`` route).

Backfill copies the current ``turn_id`` values into ``tool_call_id`` so
existing joins keep working. The old ``turn_id`` column is left in place
for one release as a deprecated alias to give safe rollback. ``ActionLogMiddleware``
keeps writing it (= ``tool_call_id``) for the same reason.

Indexes
-------

* ``ix_agent_action_log_tool_call_id`` — required by
  ``_find_action_ids_batch`` (was on ``turn_id``).
* ``ix_agent_action_log_chat_turn_id`` — required by the
  ``revert-turn/{chat_turn_id}`` query.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "135"
down_revision: str | None = "134"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agent_action_log",
        sa.Column("tool_call_id", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "agent_action_log",
        sa.Column("chat_turn_id", sa.String(length=64), nullable=True),
    )

    op.create_index(
        "ix_agent_action_log_tool_call_id",
        "agent_action_log",
        ["tool_call_id"],
    )
    op.create_index(
        "ix_agent_action_log_chat_turn_id",
        "agent_action_log",
        ["chat_turn_id"],
    )

    op.execute(
        "UPDATE agent_action_log SET tool_call_id = turn_id WHERE tool_call_id IS NULL"
    )


def downgrade() -> None:
    op.drop_index("ix_agent_action_log_chat_turn_id", table_name="agent_action_log")
    op.drop_index("ix_agent_action_log_tool_call_id", table_name="agent_action_log")
    op.drop_column("agent_action_log", "chat_turn_id")
    op.drop_column("agent_action_log", "tool_call_id")
