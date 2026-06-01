"""add external chat surface tables

Revision ID: 148
Revises: 147
Create Date: 2026-05-27

Adds the lean external chat surface schema:

* external_chat_accounts
* external_chat_bindings
* external_chat_inbound_events

External chat surfaces store Telegram-originated conversations in the existing
chat tables. This migration adds ``source`` to ``new_chat_threads`` and
``new_chat_messages`` as UI metadata while publishing all chat-message sources
through Zero so a future SurfSense UI layer can render external chats. External
chat adapter tables are served through REST in v1, so they are intentionally not
added to ``zero_publication``.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "148"
down_revision: str | None = "147"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PUBLICATION_NAME = "zero_publication"

DOCUMENT_COLS = [
    "id",
    "title",
    "document_type",
    "search_space_id",
    "folder_id",
    "created_by_id",
    "status",
    "created_at",
    "updated_at",
]

USER_COLS = [
    "id",
    "pages_limit",
    "pages_used",
    "premium_credit_micros_limit",
    "premium_credit_micros_used",
]

def _has_zero_version(conn, table: str) -> bool:
    return (
        conn.execute(
            sa.text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = :tbl AND column_name = '_0_version'"
            ),
            {"tbl": table},
        ).fetchone()
        is not None
    )


def _cols(columns: list[str]) -> str:
    return ", ".join(columns)


def _table_exists(conn, table: str) -> bool:
    return (
        conn.execute(
            sa.text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = current_schema() AND table_name = :tbl"
            ),
            {"tbl": table},
        ).fetchone()
        is not None
    )


def _column_exists(conn, table: str, column: str) -> bool:
    return (
        conn.execute(
            sa.text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_schema = current_schema() "
                "AND table_name = :tbl AND column_name = :col"
            ),
            {"tbl": table, "col": column},
        ).fetchone()
        is not None
    )


def _index_exists(conn, index_name: str) -> bool:
    return (
        conn.execute(
            sa.text(
                "SELECT 1 FROM pg_indexes "
                "WHERE schemaname = current_schema() AND indexname = :name"
            ),
            {"name": index_name},
        ).fetchone()
        is not None
    )


def _constraint_exists(conn, table: str, constraint_name: str) -> bool:
    return (
        conn.execute(
            sa.text(
                "SELECT 1 FROM information_schema.table_constraints "
                "WHERE table_schema = current_schema() "
                "AND table_name = :tbl AND constraint_name = :name"
            ),
            {"tbl": table, "name": constraint_name},
        ).fetchone()
        is not None
    )


def _drop_index_if_exists(index_name: str, table_name: str) -> None:
    if _index_exists(op.get_bind(), index_name):
        op.drop_index(index_name, table_name=table_name)


def _drop_column_if_exists(table_name: str, column_name: str) -> None:
    if _column_exists(op.get_bind(), table_name, column_name):
        op.drop_column(table_name, column_name)


def _build_set_table_ddl(
    *, documents_has_zero_ver: bool, user_has_zero_ver: bool
) -> str:
    doc_cols = DOCUMENT_COLS + (['"_0_version"'] if documents_has_zero_ver else [])
    user_cols = USER_COLS + (['"_0_version"'] if user_has_zero_ver else [])

    return (
        f"ALTER PUBLICATION {PUBLICATION_NAME} SET TABLE "
        f"notifications, "
        f"documents ({_cols(doc_cols)}), "
        f"folders, "
        f"search_source_connectors, "
        f"new_chat_messages, "
        f"chat_comments, "
        f"chat_session_state, "
        f'"user" ({_cols(user_cols)})'
    )


def _create_enum(name: str, values: tuple[str, ...]) -> postgresql.ENUM:
    enum = postgresql.ENUM(*values, name=name)
    enum.create(op.get_bind(), checkfirst=True)
    return postgresql.ENUM(*values, name=name, create_type=False)


def upgrade() -> None:
    conn = op.get_bind()
    external_chat_platform_enum = _create_enum(
        "external_chat_platform", ("telegram", "whatsapp", "signal")
    )
    external_chat_account_mode_enum = _create_enum(
        "external_chat_account_mode", ("cloud_shared", "self_host_byo")
    )
    external_chat_health_status_enum = _create_enum(
        "external_chat_health_status", ("unknown", "ok", "failing")
    )
    external_chat_binding_state_enum = _create_enum(
        "external_chat_binding_state", ("pending", "bound", "revoked", "suspended")
    )
    external_chat_peer_kind_enum = _create_enum(
        "external_chat_peer_kind", ("direct", "group", "channel", "unknown")
    )
    external_chat_event_kind_enum = _create_enum(
        "external_chat_event_kind", ("message", "edited_message", "callback_query", "other")
    )
    external_chat_event_status_enum = _create_enum(
        "external_chat_event_status",
        ("received", "processing", "processed", "ignored", "failed"),
    )

    if not _table_exists(conn, "external_chat_accounts"):
        op.create_table(
            "external_chat_accounts",
            sa.Column("id", sa.BigInteger(), primary_key=True),
            sa.Column("platform", external_chat_platform_enum, nullable=False),
            sa.Column("mode", external_chat_account_mode_enum, nullable=False),
            sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("owner_search_space_id", sa.Integer(), nullable=True),
            sa.Column("is_system_account", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("encrypted_credentials", sa.Text(), nullable=True),
            sa.Column("bot_username", sa.String(255), nullable=True),
            sa.Column("webhook_secret", sa.String(64), nullable=True),
            sa.Column(
                "cursor_state",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column(
                "health_status",
                external_chat_health_status_enum,
                nullable=False,
                server_default="unknown",
            ),
            sa.Column("last_health_check_at", sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column("suspended_at", sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column("suspended_reason", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.TIMESTAMP(timezone=True),
                nullable=False,
                server_default=sa.text("(now() AT TIME ZONE 'utc')"),
            ),
            sa.Column(
                "updated_at",
                sa.TIMESTAMP(timezone=True),
                nullable=False,
                server_default=sa.text("(now() AT TIME ZONE 'utc')"),
            ),
            sa.CheckConstraint(
                "(is_system_account = true AND owner_user_id IS NULL) OR "
                "(is_system_account = false AND owner_user_id IS NOT NULL)",
                name="ck_external_chat_accounts_owner_shape",
            ),
            sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["owner_search_space_id"], ["searchspaces.id"], ondelete="CASCADE"
            ),
        )
    op.create_index(
        "uq_external_chat_accounts_owner_platform",
        "external_chat_accounts",
        ["owner_user_id", "platform"],
        unique=True,
        postgresql_where=sa.text("is_system_account = false"),
        if_not_exists=True,
    )
    op.create_index(
        "uq_external_chat_accounts_system_platform",
        "external_chat_accounts",
        ["platform"],
        unique=True,
        postgresql_where=sa.text("is_system_account = true"),
        if_not_exists=True,
    )
    op.create_index(
        "uq_external_chat_accounts_webhook_secret",
        "external_chat_accounts",
        ["webhook_secret"],
        unique=True,
        postgresql_where=sa.text("webhook_secret IS NOT NULL"),
        if_not_exists=True,
    )

    if not _table_exists(conn, "external_chat_bindings"):
        op.create_table(
            "external_chat_bindings",
            sa.Column("id", sa.BigInteger(), primary_key=True),
            sa.Column("account_id", sa.BigInteger(), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("search_space_id", sa.Integer(), nullable=False),
            sa.Column(
                "state",
                external_chat_binding_state_enum,
                nullable=False,
                server_default="pending",
            ),
            sa.Column("pairing_code", sa.Text(), nullable=True),
            sa.Column("pairing_code_expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column("external_peer_id", sa.Text(), nullable=True),
            sa.Column(
                "external_peer_kind",
                external_chat_peer_kind_enum,
                nullable=False,
                server_default="unknown",
            ),
            sa.Column(
                "external_thread_id",
                sa.Text(),
                nullable=True,
                comment="Reserved for Telegram message_thread_id when group/forum support lands.",
            ),
            sa.Column("external_display_name", sa.Text(), nullable=True),
            sa.Column("external_username", sa.Text(), nullable=True),
            sa.Column(
                "external_metadata",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("new_chat_thread_id", sa.Integer(), nullable=True),
            sa.Column("revoked_at", sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column("suspended_at", sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column("suspended_reason", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.TIMESTAMP(timezone=True),
                nullable=False,
                server_default=sa.text("(now() AT TIME ZONE 'utc')"),
            ),
            sa.Column(
                "updated_at",
                sa.TIMESTAMP(timezone=True),
                nullable=False,
                server_default=sa.text("(now() AT TIME ZONE 'utc')"),
            ),
            sa.ForeignKeyConstraint(
                ["account_id"], ["external_chat_accounts.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["search_space_id"], ["searchspaces.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["new_chat_thread_id"], ["new_chat_threads.id"], ondelete="SET NULL"
            ),
        )
    op.create_index(
        "uq_external_chat_bindings_account_peer_active",
        "external_chat_bindings",
        ["account_id", "external_peer_id"],
        unique=True,
        postgresql_where=sa.text(
            "state IN ('bound', 'suspended') AND external_peer_id IS NOT NULL"
        ),
        if_not_exists=True,
    )
    op.create_index(
        "uq_external_chat_bindings_pairing_code_pending",
        "external_chat_bindings",
        ["pairing_code"],
        unique=True,
        postgresql_where=sa.text("state = 'pending'"),
        if_not_exists=True,
    )
    op.create_index(
        "ix_external_chat_bindings_user_state",
        "external_chat_bindings",
        ["user_id", "state"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_external_chat_bindings_search_space_state",
        "external_chat_bindings",
        ["search_space_id", "state"],
        if_not_exists=True,
    )

    if not _table_exists(conn, "external_chat_inbound_events"):
        op.create_table(
            "external_chat_inbound_events",
            sa.Column("id", sa.BigInteger(), primary_key=True),
            sa.Column("account_id", sa.BigInteger(), nullable=False),
            sa.Column("external_chat_binding_id", sa.BigInteger(), nullable=True),
            sa.Column("platform", external_chat_platform_enum, nullable=False),
            sa.Column("event_dedupe_key", sa.Text(), nullable=False),
            sa.Column("external_event_id", sa.Text(), nullable=True),
            sa.Column("external_message_id", sa.Text(), nullable=True),
            sa.Column("event_kind", external_chat_event_kind_enum, nullable=False),
            sa.Column(
                "raw_payload",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=True,
            ),
            sa.Column("request_id", sa.String(64), nullable=True),
            sa.Column(
                "status",
                external_chat_event_status_enum,
                nullable=False,
                server_default="received",
            ),
            sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column(
                "received_at",
                sa.TIMESTAMP(timezone=True),
                nullable=False,
                server_default=sa.text("(now() AT TIME ZONE 'utc')"),
            ),
            sa.Column("processed_at", sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.TIMESTAMP(timezone=True),
                nullable=False,
                server_default=sa.text("(now() AT TIME ZONE 'utc')"),
            ),
            sa.ForeignKeyConstraint(
                ["account_id"], ["external_chat_accounts.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["external_chat_binding_id"], ["external_chat_bindings.id"], ondelete="SET NULL"
            ),
            sa.UniqueConstraint(
                "account_id",
                "event_dedupe_key",
                name="uq_external_chat_inbound_account_dedupe_key",
            ),
        )
    op.create_index(
        "ix_external_chat_inbound_status_received_at",
        "external_chat_inbound_events",
        ["status", "received_at"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_external_chat_inbound_binding_received_at",
        "external_chat_inbound_events",
        ["external_chat_binding_id", "received_at"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_external_chat_inbound_request_id",
        "external_chat_inbound_events",
        ["request_id"],
        postgresql_where=sa.text("request_id IS NOT NULL"),
        if_not_exists=True,
    )

    if not _column_exists(conn, "new_chat_threads", "source"):
        op.add_column(
            "new_chat_threads",
            sa.Column("source", sa.Text(), nullable=False, server_default="surfsense"),
        )
    op.alter_column("new_chat_threads", "source", type_=sa.Text())
    if not _column_exists(conn, "new_chat_threads", "external_chat_binding_id"):
        op.add_column(
            "new_chat_threads",
            sa.Column("external_chat_binding_id", sa.BigInteger(), nullable=True),
        )
    if not _constraint_exists(
        conn, "new_chat_threads", "fk_new_chat_threads_external_chat_external_chat_binding_id"
    ):
        op.create_foreign_key(
            "fk_new_chat_threads_external_chat_external_chat_binding_id",
            "new_chat_threads",
            "external_chat_bindings",
            ["external_chat_binding_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_index("ix_new_chat_threads_source", "new_chat_threads", ["source"], if_not_exists=True)
    op.create_index(
        "ix_new_chat_threads_external_chat_binding_id",
        "new_chat_threads",
        ["external_chat_binding_id"],
        if_not_exists=True,
    )

    if not _column_exists(conn, "new_chat_messages", "source"):
        op.add_column(
            "new_chat_messages",
            sa.Column("source", sa.Text(), nullable=False, server_default="surfsense"),
        )
    op.alter_column("new_chat_messages", "source", type_=sa.Text())
    if not _column_exists(conn, "new_chat_messages", "platform_metadata"):
        op.add_column(
            "new_chat_messages",
            sa.Column("platform_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        )
    op.create_index(
        "ix_new_chat_messages_source",
        "new_chat_messages",
        ["source"],
        if_not_exists=True,
    )
    op.create_index(
        "uq_new_chat_messages_inbound_platform",
        "new_chat_messages",
        [
            "thread_id",
            sa.text("(platform_metadata->>'platform')"),
            sa.text("(platform_metadata->>'external_message_id')"),
        ],
        unique=True,
        postgresql_where=sa.text(
            "platform_metadata IS NOT NULL "
            "AND platform_metadata->>'direction' = 'inbound'"
        ),
        if_not_exists=True,
    )
    op.execute("ALTER TABLE new_chat_messages REPLICA IDENTITY FULL")

    exists = conn.execute(
        sa.text("SELECT 1 FROM pg_publication WHERE pubname = :name"),
        {"name": PUBLICATION_NAME},
    ).fetchone()
    if exists:
        documents_has_zero_ver = _has_zero_version(conn, "documents")
        user_has_zero_ver = _has_zero_version(conn, "user")
        tx = conn.begin_nested() if conn.in_transaction() else conn.begin()
        with tx:
            conn.execute(
                sa.text(
                    f"COMMENT ON PUBLICATION {PUBLICATION_NAME} IS 'pre-144-external-chat'"
                )
            )
            conn.execute(
                sa.text(
                    _build_set_table_ddl(
                        documents_has_zero_ver=documents_has_zero_ver,
                        user_has_zero_ver=user_has_zero_ver,
                    )
                )
            )
            conn.execute(
                sa.text(
                    f"COMMENT ON PUBLICATION {PUBLICATION_NAME} IS 'post-144-external-chat'"
                )
            )


def downgrade() -> None:
    conn = op.get_bind()
    exists = conn.execute(
        sa.text("SELECT 1 FROM pg_publication WHERE pubname = :name"),
        {"name": PUBLICATION_NAME},
    ).fetchone()
    if exists:
        documents_has_zero_ver = _has_zero_version(conn, "documents")
        user_has_zero_ver = _has_zero_version(conn, "user")
        # Restore the publication shape from migration 143.
        doc_cols = DOCUMENT_COLS + (['"_0_version"'] if documents_has_zero_ver else [])
        user_cols = USER_COLS + (['"_0_version"'] if user_has_zero_ver else [])
        ddl = (
            f"ALTER PUBLICATION {PUBLICATION_NAME} SET TABLE "
            f"notifications, "
            f"documents ({_cols(doc_cols)}), "
            f"folders, "
            f"search_source_connectors, "
            f"new_chat_messages, "
            f"chat_comments, "
            f"chat_session_state, "
            f'"user" ({_cols(user_cols)})'
        )
        tx = conn.begin_nested() if conn.in_transaction() else conn.begin()
        with tx:
            conn.execute(
                sa.text(f"COMMENT ON PUBLICATION {PUBLICATION_NAME} IS 'pre-144-downgrade'")
            )
            conn.execute(sa.text(ddl))
            conn.execute(
                sa.text(f"COMMENT ON PUBLICATION {PUBLICATION_NAME} IS 'post-144-downgrade'")
            )

    if _column_exists(conn, "new_chat_messages", "source"):
        op.execute("ALTER TABLE new_chat_messages REPLICA IDENTITY DEFAULT")
    _drop_index_if_exists("uq_new_chat_messages_inbound_platform", "new_chat_messages")
    _drop_index_if_exists("ix_new_chat_messages_source", "new_chat_messages")
    _drop_column_if_exists("new_chat_messages", "platform_metadata")
    _drop_column_if_exists("new_chat_messages", "source")

    _drop_index_if_exists("ix_new_chat_threads_external_chat_binding_id", "new_chat_threads")
    _drop_index_if_exists("ix_new_chat_threads_source", "new_chat_threads")
    if _constraint_exists(
        conn, "new_chat_threads", "fk_new_chat_threads_external_chat_external_chat_binding_id"
    ):
        op.drop_constraint(
            "fk_new_chat_threads_external_chat_external_chat_binding_id",
            "new_chat_threads",
            type_="foreignkey",
        )
    _drop_column_if_exists("new_chat_threads", "external_chat_binding_id")
    _drop_column_if_exists("new_chat_threads", "source")

    _drop_index_if_exists(
        "ix_external_chat_inbound_binding_received_at", "external_chat_inbound_events"
    )
    _drop_index_if_exists("ix_external_chat_inbound_request_id", "external_chat_inbound_events")
    _drop_index_if_exists("ix_external_chat_inbound_status_received_at", "external_chat_inbound_events")
    if _table_exists(conn, "external_chat_inbound_events"):
        op.drop_table("external_chat_inbound_events")

    _drop_index_if_exists(
        "ix_external_chat_bindings_search_space_state",
        "external_chat_bindings",
    )
    _drop_index_if_exists(
        "ix_external_chat_bindings_user_state", "external_chat_bindings"
    )
    _drop_index_if_exists(
        "uq_external_chat_bindings_pairing_code_pending",
        "external_chat_bindings",
    )
    _drop_index_if_exists(
        "uq_external_chat_bindings_account_peer_active",
        "external_chat_bindings",
    )
    if _table_exists(conn, "external_chat_bindings"):
        op.drop_table("external_chat_bindings")

    _drop_index_if_exists("uq_external_chat_accounts_system_platform", "external_chat_accounts")
    _drop_index_if_exists("uq_external_chat_accounts_owner_platform", "external_chat_accounts")
    _drop_index_if_exists("uq_external_chat_accounts_webhook_secret", "external_chat_accounts")
    if _table_exists(conn, "external_chat_accounts"):
        op.drop_table("external_chat_accounts")

    for enum_name in (
        "external_chat_event_status",
        "external_chat_event_kind",
        "external_chat_peer_kind",
        "external_chat_binding_state",
        "external_chat_health_status",
        "external_chat_account_mode",
        "external_chat_platform",
    ):
        postgresql.ENUM(name=enum_name).drop(conn, checkfirst=True)
