"""force zero-cache to resync after upgrading to Zero >= 1.0

Re-emits the current ``zero_publication`` shape using
``ALTER PUBLICATION ... SET TABLE`` wrapped in
``COMMENT ON PUBLICATION`` bookends. This is the publication-change
hook documented for Zero ``>=1.0``:

    https://zero.rocicorp.dev/docs/connecting-to-postgres#publication-changes

Background
----------
Migrations 117 / 139 / 140 mutated ``zero_publication`` using
``DROP PUBLICATION`` + ``CREATE PUBLICATION``. On Zero 0.26.2 that
sequence did not reliably wake the zero-cache change-streamer, so
affected installs ended up with a SQLite replica file (in the
``surfsense-zero-cache`` volume) that was snapshotted against the
pre-``user`` publication. The frontend Zero schema includes a
``userTable`` query, which then failed with
``SchemaVersionNotSupported`` and triggered the default
``onUpdateNeeded`` -> ``location.reload()`` every WebSocket keepalive
interval (~60s). See bug #1355.

This migration emits the canonical publication shape one more time,
this time using a pattern that fires Postgres event triggers and
Zero's schema-change hook. With ``ZERO_AUTO_RESET=true`` (the default)
and Zero ``>=1.0``, zero-cache responds by wiping its replica and
doing a fresh initial sync from the corrected publication.

The publication shape itself is unchanged versus migration 140 -- on
installs whose replica is already correct, this is a no-op aside
from the harmless event-trigger fire.

Revision ID: 143
Revises: 142
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "143"
down_revision: str | None = "142"
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


def _build_set_table_ddl(
    *, documents_has_zero_ver: bool, user_has_zero_ver: bool
) -> str:
    doc_cols = DOCUMENT_COLS + (['"_0_version"'] if documents_has_zero_ver else [])
    user_cols = USER_COLS + (['"_0_version"'] if user_has_zero_ver else [])
    doc_col_list = ", ".join(doc_cols)
    user_col_list = ", ".join(user_cols)
    return (
        f"ALTER PUBLICATION {PUBLICATION_NAME} SET TABLE "
        f"notifications, "
        f"documents ({doc_col_list}), "
        f"folders, "
        f"search_source_connectors, "
        f"new_chat_messages, "
        f"chat_comments, "
        f"chat_session_state, "
        f'"user" ({user_col_list})'
    )


def upgrade() -> None:
    conn = op.get_bind()

    exists = conn.execute(
        sa.text("SELECT 1 FROM pg_publication WHERE pubname = :name"),
        {"name": PUBLICATION_NAME},
    ).fetchone()
    if not exists:
        return

    documents_has_zero_ver = _has_zero_version(conn, "documents")
    user_has_zero_ver = _has_zero_version(conn, "user")

    # The COMMENT-ALTER-COMMENT trio MUST run in a single transaction so
    # Zero observes them as one schema-change event. Alembic's outer
    # transaction already covers us, but a SAVEPOINT keeps the trio
    # atomic with asyncpg, matching the pattern used in migrations
    # 117 / 139 / 140.
    tx = conn.begin_nested() if conn.in_transaction() else conn.begin()
    with tx:
        conn.execute(
            sa.text(f"COMMENT ON PUBLICATION {PUBLICATION_NAME} IS 'pre-143-resync'")
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
            sa.text(f"COMMENT ON PUBLICATION {PUBLICATION_NAME} IS 'post-143-resync'")
        )


def downgrade() -> None:
    """No-op. The publication shape is unchanged versus migration 140."""
