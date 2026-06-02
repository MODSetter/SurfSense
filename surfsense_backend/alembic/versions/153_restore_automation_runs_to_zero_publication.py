"""restore automation_runs to zero_publication

Migration 149's ``SET TABLE`` dropped ``automation_runs`` (added in 148),
breaking the dashboard live run ticker with a SchemaVersionNotSupported
reload loop. Re-emit the publication with ``automation_runs`` using the
``COMMENT`` bookend pattern so zero-cache fires its schema-change hook.

Revision ID: 153
Revises: 152
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "153"
down_revision: str | None = "152"
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


def _set_table_ddl(*, with_automation_runs: bool, conn) -> str:
    doc_cols = DOCUMENT_COLS + (['"_0_version"'] if _has_zero_version(conn, "documents") else [])
    user_cols = USER_COLS + (['"_0_version"'] if _has_zero_version(conn, "user") else [])
    tables = [
        "notifications",
        f"documents ({', '.join(doc_cols)})",
        "folders",
        "search_source_connectors",
        "new_chat_messages",
        "chat_comments",
        "chat_session_state",
        f'"user" ({", ".join(user_cols)})',
    ]
    if with_automation_runs:
        tables.append(f"automation_runs ({', '.join(AUTOMATION_RUN_COLS)})")
    return f"ALTER PUBLICATION {PUBLICATION_NAME} SET TABLE " + ", ".join(tables)


def _resync(*, with_automation_runs: bool, tag: str) -> None:
    conn = op.get_bind()
    exists = conn.execute(
        sa.text("SELECT 1 FROM pg_publication WHERE pubname = :name"),
        {"name": PUBLICATION_NAME},
    ).fetchone()
    if not exists:
        return

    tx = conn.begin_nested() if conn.in_transaction() else conn.begin()
    with tx:
        conn.execute(sa.text(f"COMMENT ON PUBLICATION {PUBLICATION_NAME} IS 'pre-{tag}'"))
        conn.execute(sa.text(_set_table_ddl(with_automation_runs=with_automation_runs, conn=conn)))
        conn.execute(sa.text(f"COMMENT ON PUBLICATION {PUBLICATION_NAME} IS 'post-{tag}'"))


def upgrade() -> None:
    _resync(with_automation_runs=True, tag="153-resync")


def downgrade() -> None:
    _resync(with_automation_runs=False, tag="153-downgrade")
