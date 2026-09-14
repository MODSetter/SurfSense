"""Erase every hosted account at T+30, after the 30-day export window closes.

The hosted service goes export-only at T-0 and its data is deleted a month
later; users are told that date in the launch email, the reminder, and on
``/sunset``. This is the script that carries it out.

It is a loop over :func:`app.account_deletion.erase_account`, which support
already uses for a single account, rather than a bulk ``DELETE``. That matters:
a raw cascade drops the rows and leaves every blob and knowledge store on disk
forever, which is the opposite of what a deletion promise means. ``erase_account``
removes documents, chunks, blobs and the knowledge store, then the user, and
forgets the Stripe customer while leaving charges and invoices for tax
(GDPR 17(3)(b)).

    # look, change nothing -- the default
    python -m scripts.purge_hosted_accounts

    # same, with every account listed
    python -m scripts.purge_hosted_accounts --verbose

    # actually erase
    python -m scripts.purge_hosted_accounts --execute

Refuses to run unless ``SUNSET_MODE`` is on, so it cannot be pointed at a live
service by accident. ``erase_account`` is idempotent, so an interrupted run is
resumed by running it again.

Runbook: ``plans/community-local/purge-runbook.md``.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from uuid import UUID

from sqlalchemy import func, select

from app.account_deletion.erase import erase_account
from app.db import User
from app.sunset import is_sunset_mode
from app.tasks.celery_tasks import get_celery_session_maker

_CONFIRM = "erase every hosted account"


async def _accounts() -> list[tuple[UUID, str]]:
    async with get_celery_session_maker()() as session:
        rows = await session.execute(select(User.id, User.email).order_by(User.email))
        return [(row[0], row[1]) for row in rows]


async def _remaining() -> int:
    async with get_celery_session_maker()() as session:
        return (await session.execute(select(func.count(User.id)))).scalar_one()


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Erase the accounts. Without this the script only reports.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the typed confirmation. For a re-run of an interrupted purge.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Stop after this many accounts. 0 means all of them.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="List every account rather than a count.",
    )
    args = parser.parse_args()

    # A purge is not reversible and the snapshot is the only way back, so the
    # guard is a refusal rather than a warning: a service still serving its
    # users is not one whose accounts should be disappearing.
    if not is_sunset_mode():
        print(
            "error: SUNSET_MODE is not set. This purge is for a service that has "
            "already wound down; set the flag on the deployment you mean to erase.",
            file=sys.stderr,
        )
        return 2

    accounts = await _accounts()
    if args.limit:
        accounts = accounts[: args.limit]

    if not accounts:
        print("Nothing to purge: no accounts remain.")
        return 0

    print(f"{len(accounts)} account(s) to erase.")
    if args.verbose:
        for user_id, email in accounts:
            print(f"  {user_id}  {email}")

    if not args.execute:
        print("\nDry run. Nothing was changed. Pass --execute to erase.")
        return 0

    if not args.yes:
        print(
            "\nThis deletes documents, chunks, blobs and knowledge stores for "
            "every account above, and cannot be undone."
        )
        typed = input(f'Type "{_CONFIRM}" to continue: ').strip()
        if typed != _CONFIRM:
            print("Aborted.", file=sys.stderr)
            return 1

    erased = 0
    failed: list[tuple[UUID, str, str]] = []
    for user_id, email in accounts:
        try:
            await erase_account(user_id)
        except Exception as exc:
            # Recorded and reported rather than raised: stopping here would
            # leave the rest of the purge undone and the date already passed.
            failed.append((user_id, email, str(exc)))
            print(f"  FAILED  {user_id}  {email}: {exc}", file=sys.stderr)
            continue
        erased += 1
        if erased % 100 == 0:
            print(f"  erased {erased}/{len(accounts)}")

    print(f"\nErased {erased} account(s).")
    if failed:
        print(f"{len(failed)} failed:", file=sys.stderr)
        for user_id, email, exc in failed:
            print(f"  {user_id}  {email}: {exc}", file=sys.stderr)
        print(
            "\nerase_account is safe to run twice; re-run to retry the failures.",
            file=sys.stderr,
        )

    print(f"{await _remaining()} account(s) remain.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
