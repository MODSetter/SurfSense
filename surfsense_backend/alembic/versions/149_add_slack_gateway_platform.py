"""add slack gateway platform

Revision ID: 149
Revises: 148
Create Date: 2026-05-31
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "149"
down_revision: str | None = "148"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enum_value_exists(enum_name: str, value: str) -> bool:
    conn = op.get_bind()
    return (
        conn.execute(
            sa.text(
                "SELECT 1 FROM pg_enum e "
                "JOIN pg_type t ON t.oid = e.enumtypid "
                "WHERE t.typname = :enum_name AND e.enumlabel = :value"
            ),
            {"enum_name": enum_name, "value": value},
        ).fetchone()
        is not None
    )


def _index_exists(index_name: str) -> bool:
    conn = op.get_bind()
    return (
        conn.execute(
            sa.text(
                "SELECT 1 FROM pg_indexes "
                "WHERE schemaname = current_schema() AND indexname = :index_name"
            ),
            {"index_name": index_name},
        ).fetchone()
        is not None
    )


def upgrade() -> None:
    if not _enum_value_exists("external_chat_platform", "slack"):
        op.execute("ALTER TYPE external_chat_platform ADD VALUE 'slack'")

    if _index_exists("uq_external_chat_accounts_system_platform"):
        op.drop_index(
            "uq_external_chat_accounts_system_platform",
            table_name="external_chat_accounts",
        )

    op.create_index(
        "uq_external_chat_accounts_system_platform",
        "external_chat_accounts",
        ["platform"],
        unique=True,
        postgresql_where=sa.text(
            "is_system_account = true AND NOT (cursor_state ? 'team_id')"
        ),
        if_not_exists=True,
    )
    op.create_index(
        "uq_external_chat_accounts_slack_team",
        "external_chat_accounts",
        ["platform", sa.text("(cursor_state ->> 'team_id')")],
        unique=True,
        postgresql_where=sa.text(
            "is_system_account = true AND cursor_state ? 'team_id'"
        ),
        if_not_exists=True,
    )


def downgrade() -> None:
    if _index_exists("uq_external_chat_accounts_slack_team"):
        op.drop_index(
            "uq_external_chat_accounts_slack_team",
            table_name="external_chat_accounts",
        )
    if _index_exists("uq_external_chat_accounts_system_platform"):
        op.drop_index(
            "uq_external_chat_accounts_system_platform",
            table_name="external_chat_accounts",
        )
    op.create_index(
        "uq_external_chat_accounts_system_platform",
        "external_chat_accounts",
        ["platform"],
        unique=True,
        postgresql_where=sa.text("is_system_account = true"),
        if_not_exists=True,
    )
    # PostgreSQL enum values are intentionally not removed on downgrade.
