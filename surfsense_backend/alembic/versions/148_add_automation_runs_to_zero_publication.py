"""add automation_runs to zero_publication with thin column list

Publishes ``automation_runs`` so the dashboard can replace polling with a
live run status + per-step ticker. Only the columns the list and ticker
read are exposed (``id, automation_id, trigger_id, status, step_results,
started_at, finished_at, created_at``); heavy JSONB
(``definition_snapshot``, ``inputs``, ``output``, ``artifacts``, ``error``)
stays on REST and is fetched lazily on detail expand.

Uses the canonical ``ALTER PUBLICATION ... SET TABLE`` + ``COMMENT``
bookend pattern (see migration 143) -- the shape Zero ``>=1.0`` requires
to fire its schema-change hook. Existing tables are re-emitted unchanged.

Revision ID: 148
Revises: 147
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "148"
down_revision: str | None = "147"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PUBLICATION_NAME = "zero_publication"

# Mirrors migration 143. Kept in sync explicitly: any change to these lists
# must be re-emitted in a new resync migration with COMMENT bookends.
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

# Thin set: status + lightweight progress only. Heavy JSONB stays on REST.
AUTOMATION_RUN_COLS = [
    "id",
    "automation_id",
    "trigger_id",
    "status",
    "step_results",
    "started_at",
    "finished_at",
    "created_at",
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
    run_col_list = ", ".join(AUTOMATION_RUN_COLS)
    return (
        f"ALTER PUBLICATION {PUBLICATION_NAME} SET TABLE "
        f"notifications, "
        f"documents ({doc_col_list}), "
        f"folders, "
        f"search_source_connectors, "
        f"new_chat_messages, "
        f"chat_comments, "
        f"chat_session_state, "
        f'"user" ({user_col_list}), '
        f"automation_runs ({run_col_list})"
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

    # COMMENT-ALTER-COMMENT trio must be one transaction so Zero observes
    # them as one schema-change event. Matches the SAVEPOINT pattern used
    # in migrations 117 / 139 / 140 / 143.
    tx = conn.begin_nested() if conn.in_transaction() else conn.begin()
    with tx:
        conn.execute(
            sa.text(f"COMMENT ON PUBLICATION {PUBLICATION_NAME} IS 'pre-148-resync'")
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
            sa.text(f"COMMENT ON PUBLICATION {PUBLICATION_NAME} IS 'post-148-resync'")
        )


def downgrade() -> None:
    """Re-emit migration 143's shape (no automation_runs)."""
    conn = op.get_bind()

    exists = conn.execute(
        sa.text("SELECT 1 FROM pg_publication WHERE pubname = :name"),
        {"name": PUBLICATION_NAME},
    ).fetchone()
    if not exists:
        return

    documents_has_zero_ver = _has_zero_version(conn, "documents")
    user_has_zero_ver = _has_zero_version(conn, "user")

    doc_cols = DOCUMENT_COLS + (['"_0_version"'] if documents_has_zero_ver else [])
    user_cols = USER_COLS + (['"_0_version"'] if user_has_zero_ver else [])
    doc_col_list = ", ".join(doc_cols)
    user_col_list = ", ".join(user_cols)
    ddl = (
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

    tx = conn.begin_nested() if conn.in_transaction() else conn.begin()
    with tx:
        conn.execute(
            sa.text(f"COMMENT ON PUBLICATION {PUBLICATION_NAME} IS 'pre-148-downgrade'")
        )
        conn.execute(sa.text(ddl))
        conn.execute(
            sa.text(
                f"COMMENT ON PUBLICATION {PUBLICATION_NAME} IS 'post-148-downgrade'"
            )
        )
