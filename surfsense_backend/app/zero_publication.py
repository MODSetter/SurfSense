"""Canonical Zero publication definition for SurfSense.

This module is the single source of truth for ``zero_publication``. Future
publication changes should update ``ZERO_PUBLICATION`` and call
``apply_publication()`` from a migration instead of hand-copying table lists.

SurfSense runs Zero on Postgres with Zero's event triggers installed, so the
official Zero path is a plain ``ALTER PUBLICATION ... SET TABLE``. If a future
deployment cannot use event triggers, use Zero's documented
``zero_0.update_schemas()`` hook as the fallback instead of COMMENT bookends.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections.abc import Mapping, Sequence

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

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
    "credit_micros_balance",
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

ZERO_PUBLICATION: Mapping[str, Sequence[str] | None] = {
    "notifications": None,
    "documents": DOCUMENT_COLS,
    "folders": None,
    "search_source_connectors": None,
    "new_chat_messages": None,
    "chat_comments": None,
    "chat_session_state": None,
    "user": USER_COLS,
    "automation_runs": AUTOMATION_RUN_COLS,
}


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _column_exists(conn: Connection, table: str, column: str) -> bool:
    return (
        conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_schema = current_schema() "
                "AND table_name = :table AND column_name = :column"
            ),
            {"table": table, "column": column},
        ).fetchone()
        is not None
    )


def _expected_columns(conn: Connection, table: str) -> list[str] | None:
    columns = ZERO_PUBLICATION[table]
    if columns is None:
        return None

    expected = list(columns)
    if table in {"documents", "user"} and _column_exists(conn, table, "_0_version"):
        expected.append("_0_version")
    return expected


def _format_table_entry(conn: Connection, table: str) -> str:
    columns = _expected_columns(conn, table)
    table_sql = _quote_identifier(table)
    if columns is None:
        return table_sql

    column_sql = ", ".join(_quote_identifier(column) for column in columns)
    return f"{table_sql} ({column_sql})"


def build_set_table_sql(conn: Connection) -> str:
    """Build the canonical plain SET TABLE statement for Zero's event triggers."""

    table_list = ", ".join(
        _format_table_entry(conn, table) for table in ZERO_PUBLICATION
    )
    return f"ALTER PUBLICATION {_quote_identifier(PUBLICATION_NAME)} SET TABLE {table_list}"


def apply_publication(conn: Connection) -> None:
    """Reconcile ``zero_publication`` to the canonical shape."""

    exists = conn.execute(
        text("SELECT 1 FROM pg_publication WHERE pubname = :name"),
        {"name": PUBLICATION_NAME},
    ).fetchone()
    if not exists:
        return

    conn.execute(text(build_set_table_sql(conn)))


def _actual_publication_shape(conn: Connection) -> dict[str, list[str] | None]:
    rows = conn.execute(
        text(
            "SELECT pt.tablename, pr.prattrs IS NULL AS all_columns, pt.attnames "
            "FROM pg_publication_tables pt "
            "JOIN pg_publication p ON p.pubname = pt.pubname "
            "JOIN pg_class c ON c.relname = pt.tablename "
            "JOIN pg_namespace n ON n.oid = c.relnamespace AND n.nspname = pt.schemaname "
            "JOIN pg_publication_rel pr ON pr.prpubid = p.oid AND pr.prrelid = c.oid "
            "WHERE pt.pubname = :name AND pt.schemaname = current_schema() "
            "ORDER BY pt.tablename"
        ),
        {"name": PUBLICATION_NAME},
    ).mappings()

    return {
        str(row["tablename"]): None
        if row["all_columns"]
        else list(row["attnames"] or [])
        for row in rows
    }


def expected_publication_shape(conn: Connection) -> dict[str, list[str] | None]:
    return {table: _expected_columns(conn, table) for table in ZERO_PUBLICATION}


def verify_publication(conn: Connection) -> list[str]:
    """Return human-readable mismatches between Postgres and the canonical shape."""

    publication_exists = conn.execute(
        text("SELECT 1 FROM pg_publication WHERE pubname = :name"),
        {"name": PUBLICATION_NAME},
    ).fetchone()
    if not publication_exists:
        return [f"Publication {PUBLICATION_NAME!r} does not exist"]

    actual = _actual_publication_shape(conn)
    expected = expected_publication_shape(conn)
    mismatches: list[str] = []

    for table, expected_columns in expected.items():
        if table not in actual:
            mismatches.append(f"{table}: missing from publication")
            continue

        actual_columns = actual[table]
        actual_key = sorted(actual_columns) if actual_columns is not None else None
        expected_key = (
            sorted(expected_columns) if expected_columns is not None else None
        )
        if actual_key != expected_key:
            mismatches.append(
                f"{table}: expected columns {expected_columns or 'ALL'}, "
                f"got {actual_columns or 'ALL'}"
            )

    for table in sorted(set(actual) - set(expected)):
        mismatches.append(f"{table}: unexpected table in publication")

    return mismatches


async def _verify_cli() -> int:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL is required to verify zero_publication.", file=sys.stderr)
        return 2

    engine = create_async_engine(database_url)
    async with engine.connect() as async_conn:

        def run_verify(sync_conn: Connection) -> list[str]:
            return verify_publication(sync_conn)

        mismatches = await async_conn.run_sync(run_verify)

    await engine.dispose()

    if mismatches:
        print("zero_publication shape mismatch:", file=sys.stderr)
        for mismatch in mismatches:
            print(f"  - {mismatch}", file=sys.stderr)
        return 1

    print("zero_publication shape verified.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage SurfSense's Zero publication")
    parser.add_argument(
        "--verify", action="store_true", help="verify zero_publication shape"
    )
    args = parser.parse_args()

    if args.verify:
        return asyncio.run(_verify_cli())

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
