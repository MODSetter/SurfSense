"""remove document summary llm settings

Revision ID: 154
Revises: 153
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "154"
down_revision: str | None = "153"
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


def _column_exists(conn, table: str, column: str) -> bool:
    return (
        conn.execute(
            sa.text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = :table AND column_name = :column"
            ),
            {"table": table, "column": column},
        ).fetchone()
        is not None
    )


def _has_zero_version(conn, table: str) -> bool:
    return _column_exists(conn, table, "_0_version")


def _set_table_ddl(conn) -> str:
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
        f"automation_runs ({', '.join(AUTOMATION_RUN_COLS)})",
    ]
    return f"ALTER PUBLICATION {PUBLICATION_NAME} SET TABLE " + ", ".join(tables)


def _resync_zero_publication(tag: str) -> None:
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
        conn.execute(sa.text(_set_table_ddl(conn)))
        conn.execute(sa.text(f"COMMENT ON PUBLICATION {PUBLICATION_NAME} IS 'post-{tag}'"))


def upgrade() -> None:
    conn = op.get_bind()

    if _column_exists(conn, "searchspaces", "document_summary_llm_id"):
        op.drop_column("searchspaces", "document_summary_llm_id")

    if _column_exists(conn, "search_source_connectors", "enable_summary"):
        op.drop_column("search_source_connectors", "enable_summary")

    _resync_zero_publication("154-summary-removal")


def downgrade() -> None:
    conn = op.get_bind()

    if not _column_exists(conn, "searchspaces", "document_summary_llm_id"):
        op.add_column(
            "searchspaces",
            sa.Column("document_summary_llm_id", sa.Integer(), nullable=True, server_default="0"),
        )

    if not _column_exists(conn, "search_source_connectors", "enable_summary"):
        op.add_column(
            "search_source_connectors",
            sa.Column(
                "enable_summary",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )

    _resync_zero_publication("154-summary-removal-downgrade")
