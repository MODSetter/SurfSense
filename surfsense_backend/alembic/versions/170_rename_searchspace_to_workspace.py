"""rename searchspace schema to workspace

Physically renames the SearchSpace schema to WorkSpace: tables, the
``search_space_id`` / ``owner_search_space_id`` columns, the named
constraints/indexes/sequences that embed the old name, and the auto-named
FK/PK/sequence objects. The Zero publication is reconciled to the renamed
``workspace_id`` column lists via the blessed ``apply_publication`` path
(never raw DROP/CREATE PUBLICATION -- see migration 116).

This is the existing-deployment upgrade path (chains after head 169). The
from-scratch ``alembic upgrade head`` path is a separate, pre-existing concern
(0_initial uses create_all of the current ORM); it is out of scope here.

Revision ID: 170
Revises: 169
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.zero_publication import apply_publication

revision: str = "170"
down_revision: str | None = "169"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PUBLICATION_NAME = "zero_publication"

# Tables whose published column list references the renamed column. Their
# column-list dependency must be removed before RENAME COLUMN is permitted,
# then re-added by apply_publication with the new column name.
PUBLICATION_COLUMN_LIST_TABLES = [
    "documents",
    "automations",
    "new_chat_threads",
    "podcasts",
]

# (old_table, new_table)
TABLE_RENAMES: list[tuple[str, str]] = [
    ("searchspaces", "workspaces"),
    ("search_space_roles", "workspace_roles"),
    ("search_space_memberships", "workspace_memberships"),
    ("search_space_invites", "workspace_invites"),
]

# (table, old_column, new_column) -- table names are POST-table-rename.
COLUMN_RENAMES: list[tuple[str, str, str]] = [
    ("agent_action_log", "search_space_id", "workspace_id"),
    ("agent_permission_rules", "search_space_id", "workspace_id"),
    ("automations", "search_space_id", "workspace_id"),
    ("connections", "search_space_id", "workspace_id"),
    ("document_files", "search_space_id", "workspace_id"),
    ("document_revisions", "search_space_id", "workspace_id"),
    ("documents", "search_space_id", "workspace_id"),
    ("external_chat_bindings", "search_space_id", "workspace_id"),
    ("folder_revisions", "search_space_id", "workspace_id"),
    ("folders", "search_space_id", "workspace_id"),
    ("image_generations", "search_space_id", "workspace_id"),
    ("logs", "search_space_id", "workspace_id"),
    ("new_chat_threads", "search_space_id", "workspace_id"),
    ("notifications", "search_space_id", "workspace_id"),
    ("podcasts", "search_space_id", "workspace_id"),
    ("prompts", "search_space_id", "workspace_id"),
    ("reports", "search_space_id", "workspace_id"),
    ("search_source_connectors", "search_space_id", "workspace_id"),
    ("token_usage", "search_space_id", "workspace_id"),
    ("video_presentations", "search_space_id", "workspace_id"),
    ("external_chat_accounts", "owner_search_space_id", "owner_workspace_id"),
    ("workspace_roles", "search_space_id", "workspace_id"),
    ("workspace_memberships", "search_space_id", "workspace_id"),
    ("workspace_invites", "search_space_id", "workspace_id"),
]

# (table, old_constraint, new_constraint) -- table names are POST-table-rename.
CONSTRAINT_RENAMES: list[tuple[str, str, str]] = [
    (
        "agent_action_log",
        "agent_action_log_search_space_id_fkey",
        "agent_action_log_workspace_id_fkey",
    ),
    (
        "agent_permission_rules",
        "agent_permission_rules_search_space_id_fkey",
        "agent_permission_rules_workspace_id_fkey",
    ),
    (
        "automations",
        "automations_search_space_id_fkey",
        "automations_workspace_id_fkey",
    ),
    (
        "connections",
        "connections_search_space_id_fkey",
        "connections_workspace_id_fkey",
    ),
    (
        "document_files",
        "document_files_search_space_id_fkey",
        "document_files_workspace_id_fkey",
    ),
    (
        "document_revisions",
        "document_revisions_search_space_id_fkey",
        "document_revisions_workspace_id_fkey",
    ),
    ("documents", "documents_search_space_id_fkey", "documents_workspace_id_fkey"),
    (
        "external_chat_accounts",
        "external_chat_accounts_owner_search_space_id_fkey",
        "external_chat_accounts_owner_workspace_id_fkey",
    ),
    (
        "external_chat_bindings",
        "external_chat_bindings_search_space_id_fkey",
        "external_chat_bindings_workspace_id_fkey",
    ),
    (
        "folder_revisions",
        "folder_revisions_search_space_id_fkey",
        "folder_revisions_workspace_id_fkey",
    ),
    ("folders", "folders_search_space_id_fkey", "folders_workspace_id_fkey"),
    (
        "image_generations",
        "image_generations_search_space_id_fkey",
        "image_generations_workspace_id_fkey",
    ),
    ("logs", "logs_search_space_id_fkey", "logs_workspace_id_fkey"),
    (
        "new_chat_threads",
        "new_chat_threads_search_space_id_fkey",
        "new_chat_threads_workspace_id_fkey",
    ),
    (
        "notifications",
        "notifications_search_space_id_fkey",
        "notifications_workspace_id_fkey",
    ),
    ("podcasts", "podcasts_search_space_id_fkey", "podcasts_workspace_id_fkey"),
    ("prompts", "prompts_search_space_id_fkey", "prompts_workspace_id_fkey"),
    ("reports", "reports_search_space_id_fkey", "reports_workspace_id_fkey"),
    (
        "search_source_connectors",
        "search_source_connectors_search_space_id_fkey",
        "search_source_connectors_workspace_id_fkey",
    ),
    (
        "search_source_connectors",
        "uq_searchspace_user_connector_type_name",
        "uq_workspace_user_connector_type_name",
    ),
    (
        "token_usage",
        "token_usage_search_space_id_fkey",
        "token_usage_workspace_id_fkey",
    ),
    (
        "video_presentations",
        "video_presentations_search_space_id_fkey",
        "video_presentations_workspace_id_fkey",
    ),
    (
        "workspace_invites",
        "search_space_invites_created_by_id_fkey",
        "workspace_invites_created_by_id_fkey",
    ),
    (
        "workspace_invites",
        "search_space_invites_pkey",
        "workspace_invites_pkey",
    ),
    (
        "workspace_invites",
        "search_space_invites_role_id_fkey",
        "workspace_invites_role_id_fkey",
    ),
    (
        "workspace_invites",
        "search_space_invites_search_space_id_fkey",
        "workspace_invites_workspace_id_fkey",
    ),
    (
        "workspace_memberships",
        "search_space_memberships_invited_by_invite_id_fkey",
        "workspace_memberships_invited_by_invite_id_fkey",
    ),
    (
        "workspace_memberships",
        "search_space_memberships_pkey",
        "workspace_memberships_pkey",
    ),
    (
        "workspace_memberships",
        "search_space_memberships_role_id_fkey",
        "workspace_memberships_role_id_fkey",
    ),
    (
        "workspace_memberships",
        "search_space_memberships_search_space_id_fkey",
        "workspace_memberships_workspace_id_fkey",
    ),
    (
        "workspace_memberships",
        "search_space_memberships_user_id_fkey",
        "workspace_memberships_user_id_fkey",
    ),
    (
        "workspace_memberships",
        "uq_user_searchspace_membership",
        "uq_user_workspace_membership",
    ),
    (
        "workspace_roles",
        "search_space_roles_pkey",
        "workspace_roles_pkey",
    ),
    (
        "workspace_roles",
        "search_space_roles_search_space_id_fkey",
        "workspace_roles_workspace_id_fkey",
    ),
    (
        "workspace_roles",
        "uq_searchspace_role_name",
        "uq_workspace_role_name",
    ),
    ("workspaces", "searchspaces_pkey", "workspaces_pkey"),
    ("workspaces", "searchspaces_user_id_fkey", "workspaces_user_id_fkey"),
]

# (old_index, new_index) -- plain indexes only; PK/unique-backed indexes follow
# their RENAME CONSTRAINT above. ALTER INDEX IF EXISTS covers both create_all
# indexes and the runtime ``setup_indexes()`` ones (idx_documents_*).
INDEX_RENAMES: list[tuple[str, str]] = [
    ("ix_agent_action_log_search_space_id", "ix_agent_action_log_workspace_id"),
    (
        "ix_agent_permission_rules_search_space_id",
        "ix_agent_permission_rules_workspace_id",
    ),
    ("ix_automations_search_space_id", "ix_automations_workspace_id"),
    ("ix_document_files_search_space_id", "ix_document_files_workspace_id"),
    ("ix_document_revisions_search_space_id", "ix_document_revisions_workspace_id"),
    (
        "ix_external_chat_bindings_search_space_state",
        "ix_external_chat_bindings_workspace_state",
    ),
    ("ix_folder_revisions_search_space_id", "ix_folder_revisions_workspace_id"),
    ("ix_folders_search_space_id", "ix_folders_workspace_id"),
    ("ix_notifications_search_space_id", "ix_notifications_workspace_id"),
    ("ix_notifications_user_space_created", "ix_notifications_user_workspace_created"),
    ("ix_prompts_search_space_id", "ix_prompts_workspace_id"),
    ("ix_token_usage_search_space_id", "ix_token_usage_workspace_id"),
    ("ix_search_space_invites_created_at", "ix_workspace_invites_created_at"),
    ("ix_search_space_invites_id", "ix_workspace_invites_id"),
    ("ix_search_space_invites_invite_code", "ix_workspace_invites_invite_code"),
    ("ix_search_space_memberships_created_at", "ix_workspace_memberships_created_at"),
    ("ix_search_space_memberships_id", "ix_workspace_memberships_id"),
    ("ix_search_space_roles_created_at", "ix_workspace_roles_created_at"),
    ("ix_search_space_roles_id", "ix_workspace_roles_id"),
    ("ix_search_space_roles_name", "ix_workspace_roles_name"),
    ("ix_searchspaces_created_at", "ix_workspaces_created_at"),
    ("ix_searchspaces_id", "ix_workspaces_id"),
    ("ix_searchspaces_name", "ix_workspaces_name"),
    ("idx_documents_search_space_id", "idx_documents_workspace_id"),
    ("idx_documents_search_space_updated", "idx_documents_workspace_updated"),
]

# (old_sequence, new_sequence)
SEQUENCE_RENAMES: list[tuple[str, str]] = [
    ("searchspaces_id_seq", "workspaces_id_seq"),
    ("search_space_roles_id_seq", "workspace_roles_id_seq"),
    ("search_space_memberships_id_seq", "workspace_memberships_id_seq"),
    ("search_space_invites_id_seq", "workspace_invites_id_seq"),
]

# ---- Hardcoded OLD-shape publication (for downgrade only; finding 7). ----
# Mirrors app.zero_publication.ZERO_PUBLICATION at revision 169 but with the
# pre-rename ``search_space_id`` column. NEVER import the live module here: it
# now reflects ``workspace_id`` and would silently drop the column-list tables.
_DOWNGRADE_DOCUMENT_COLS = [
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
_DOWNGRADE_USER_COLS = ["id", "credit_micros_balance"]
_DOWNGRADE_AUTOMATION_RUN_COLS = [
    "id",
    "automation_id",
    "trigger_id",
    "status",
    "step_results",
    "started_at",
    "finished_at",
    "created_at",
]
_DOWNGRADE_AUTOMATION_COLS = ["id", "search_space_id"]
_DOWNGRADE_NEW_CHAT_THREAD_COLS = ["id", "search_space_id"]
_DOWNGRADE_PODCAST_COLS = [
    "id",
    "title",
    "status",
    "spec",
    "spec_version",
    "duration_seconds",
    "error",
    "search_space_id",
    "thread_id",
    "created_at",
]
# Ordered to match ZERO_PUBLICATION; None == all columns.
_DOWNGRADE_PUBLICATION: list[tuple[str, list[str] | None]] = [
    ("notifications", None),
    ("documents", _DOWNGRADE_DOCUMENT_COLS),
    ("folders", None),
    ("search_source_connectors", None),
    ("new_chat_threads", _DOWNGRADE_NEW_CHAT_THREAD_COLS),
    ("new_chat_messages", None),
    ("chat_comments", None),
    ("chat_session_state", None),
    ("user", _DOWNGRADE_USER_COLS),
    ("automations", _DOWNGRADE_AUTOMATION_COLS),
    ("automation_runs", _DOWNGRADE_AUTOMATION_RUN_COLS),
    ("podcasts", _DOWNGRADE_PODCAST_COLS),
]


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _publication_exists(conn) -> bool:
    return (
        conn.execute(
            sa.text("SELECT 1 FROM pg_publication WHERE pubname = :n"),
            {"n": PUBLICATION_NAME},
        ).fetchone()
        is not None
    )


def _is_publication_member(conn, table: str) -> bool:
    return (
        conn.execute(
            sa.text(
                "SELECT 1 FROM pg_publication_tables "
                "WHERE pubname = :n AND schemaname = current_schema() "
                "AND tablename = :t"
            ),
            {"n": PUBLICATION_NAME, "t": table},
        ).fetchone()
        is not None
    )


def _table_columns(conn, table: str) -> set[str]:
    rows = conn.execute(
        sa.text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = current_schema() AND table_name = :t"
        ),
        {"t": table},
    ).fetchall()
    return {row[0] for row in rows}


def _neutralize_column_list_tables(conn) -> None:
    """Remove the column-list dependency so RENAME COLUMN is permitted."""
    if not _publication_exists(conn):
        return
    for table in PUBLICATION_COLUMN_LIST_TABLES:
        if _is_publication_member(conn, table):
            conn.execute(
                sa.text(f"ALTER PUBLICATION {_quote(PUBLICATION_NAME)} DROP TABLE {table}")
            )


def _rename_table(conn, old: str, new: str) -> None:
    conn.execute(sa.text(f"ALTER TABLE IF EXISTS {old} RENAME TO {new}"))


def _rename_column(conn, table: str, old: str, new: str) -> None:
    conn.execute(
        sa.text(
            f"""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = current_schema()
                      AND table_name = '{table}' AND column_name = '{old}'
                ) THEN
                    ALTER TABLE {table} RENAME COLUMN {old} TO {new};
                END IF;
            END$$;
            """
        )
    )


def _rename_constraint(conn, table: str, old: str, new: str) -> None:
    conn.execute(
        sa.text(
            f"""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = '{old}'
                      AND conrelid = to_regclass('{table}')
                ) THEN
                    ALTER TABLE {table} RENAME CONSTRAINT {old} TO {new};
                END IF;
            END$$;
            """
        )
    )


def _rename_index(conn, old: str, new: str) -> None:
    conn.execute(sa.text(f"ALTER INDEX IF EXISTS {old} RENAME TO {new}"))


def _rename_sequence(conn, old: str, new: str) -> None:
    conn.execute(sa.text(f"ALTER SEQUENCE IF EXISTS {old} RENAME TO {new}"))


def _restore_downgrade_publication(conn) -> None:
    """Re-emit the OLD (search_space_id) publication shape via plain SET TABLE.

    Does NOT call apply_publication (which reads the live, now-workspace_id
    module) -- that would silently drop the column-list tables (finding 7).
    """
    if not _publication_exists(conn):
        return
    # Drop the column-list tables first so the SET TABLE has no stale
    # workspace_id dependency to trip over.
    for table in PUBLICATION_COLUMN_LIST_TABLES:
        if _is_publication_member(conn, table):
            conn.execute(
                sa.text(f"ALTER PUBLICATION {_quote(PUBLICATION_NAME)} DROP TABLE {table}")
            )

    entries: list[str] = []
    for table, cols in _DOWNGRADE_PUBLICATION:
        actual = _table_columns(conn, table)
        if not actual:
            continue
        if cols is None:
            entries.append(_quote(table))
            continue
        expected = list(cols)
        if table in {"documents", "user", "podcasts"} and "_0_version" in actual:
            expected.append("_0_version")
        if any(col not in actual for col in expected):
            continue
        col_sql = ", ".join(_quote(col) for col in expected)
        entries.append(f"{_quote(table)} ({col_sql})")

    table_list = ", ".join(entries)
    conn.execute(
        sa.text(f"ALTER PUBLICATION {_quote(PUBLICATION_NAME)} SET TABLE {table_list}")
    )


def upgrade() -> None:
    conn = op.get_bind()

    _neutralize_column_list_tables(conn)

    for old, new in TABLE_RENAMES:
        _rename_table(conn, old, new)
    for table, old, new in COLUMN_RENAMES:
        _rename_column(conn, table, old, new)
    for table, old, new in CONSTRAINT_RENAMES:
        _rename_constraint(conn, table, old, new)
    for old, new in INDEX_RENAMES:
        _rename_index(conn, old, new)
    for old, new in SEQUENCE_RENAMES:
        _rename_sequence(conn, old, new)

    # Reconcile to the new workspace_id shape (blessed SET TABLE path); no-op
    # if the publication does not exist.
    apply_publication(conn)


def downgrade() -> None:
    conn = op.get_bind()

    _neutralize_column_list_tables(conn)

    for old, new in SEQUENCE_RENAMES:
        _rename_sequence(conn, new, old)
    for old, new in INDEX_RENAMES:
        _rename_index(conn, new, old)
    for table, old, new in CONSTRAINT_RENAMES:
        # table here is the POST-rename name; constraints/tables are still
        # renamed at this point (table rename is reversed last).
        _rename_constraint(conn, table, new, old)
    for table, old, new in COLUMN_RENAMES:
        _rename_column(conn, table, new, old)
    for old, new in TABLE_RENAMES:
        _rename_table(conn, new, old)

    _restore_downgrade_publication(conn)
