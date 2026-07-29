"""Fleet runner for the Phase 5 knowledge-store migration.

Dry run by default: reports parity per workspace, writes nothing. Re-run with
--yes to seed for real. Every report is appended to a JSONL file, so a fleet
pass is resumable and auditable; re-seeding is idempotent and convergent, so
re-running after a partial pass only heals.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict
from datetime import UTC, datetime

from sqlalchemy import select

from app.db import Workspace, async_session_maker
from app.knowledge_store.migrate import migrate_workspace


async def _workspace_ids(only: list[int]) -> list[int]:
    if only:
        return only
    async with async_session_maker() as session:
        rows = await session.execute(select(Workspace.id).order_by(Workspace.id))
        return [row[0] for row in rows]


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Actually seed. Without this flag the command is a parity dry run.",
    )
    parser.add_argument(
        "--workspace",
        type=int,
        action="append",
        default=[],
        help="Limit to this workspace id (repeatable). Default: all workspaces.",
    )
    parser.add_argument(
        "--out",
        default="knowledge_store_migration_reports.jsonl",
        help="JSONL file the per-workspace reports are appended to.",
    )
    args = parser.parse_args()

    ids = await _workspace_ids(args.workspace)
    ok = failed = 0
    with open(args.out, "a") as out:
        for workspace_id in ids:
            # Fresh session per workspace: one failed workspace must not
            # poison the session the rest of the fleet reads through.
            async with async_session_maker() as session:
                report = await migrate_workspace(
                    session, workspace_id, dry_run=not args.yes
                )
            out.write(
                json.dumps(
                    {"at": datetime.now(UTC).isoformat(), **asdict(report)}
                )
                + "\n"
            )
            out.flush()
            ok += report.ok
            failed += not report.ok
            if report.ok:
                status = "ok"
            elif report.error:
                status = f"error: {report.error}"
            else:
                # Expected on a pre-seed dry run: everything reads as missing.
                status = (
                    f"drift: missing={len(report.missing)}"
                    f" extra={len(report.extra)}"
                    f" mismatched={len(report.mismatched)}"
                )
            print(f"workspace {workspace_id}: {status}, {report.files} file(s)")

    mode = "seeded" if args.yes else "dry run"
    print(f"{mode}: {ok} ok, {failed} failed of {len(ids)}; reports in {args.out}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
