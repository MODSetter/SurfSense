"""add discord gateway platform

Revision ID: 150
Revises: 149
Create Date: 2026-06-01
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "150"
down_revision: str | None = "149"
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
    if not _enum_value_exists("external_chat_platform", "discord"):
        op.execute("ALTER TYPE external_chat_platform ADD VALUE 'discord'")

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
            "is_system_account = true "
            "AND NOT (cursor_state ? 'team_id') "
            "AND NOT (cursor_state ? 'guild_id')"
        ),
        if_not_exists=True,
    )
    op.create_index(
        "uq_external_chat_accounts_discord_guild",
        "external_chat_accounts",
        ["platform", sa.text("(cursor_state ->> 'guild_id')")],
        unique=True,
        postgresql_where=sa.text(
            "is_system_account = true AND cursor_state ? 'guild_id'"
        ),
        if_not_exists=True,
    )


def downgrade() -> None:
    if _index_exists("uq_external_chat_accounts_discord_guild"):
        op.drop_index(
            "uq_external_chat_accounts_discord_guild",
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
        postgresql_where=sa.text(
            "is_system_account = true AND NOT (cursor_state ? 'team_id')"
        ),
        if_not_exists=True,
    )
    # PostgreSQL enum values are intentionally not removed on downgrade.
