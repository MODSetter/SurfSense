"""One-shot cutover helper to revoke every refresh token.

Run with --yes during the auth-hardening cutover, alongside setting
MIN_ISSUED_AT to the deploy epoch.
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import text

from app.db import async_session_maker


async def _count_active_tokens() -> int:
    async with async_session_maker() as session:
        result = await session.execute(
            text(
                """
                SELECT count(*)
                FROM refresh_tokens
                WHERE revoked_at IS NULL
                  AND expires_at > NOW()
                """
            )
        )
        return int(result.scalar_one())


async def _revoke_all_tokens() -> int:
    async with async_session_maker() as session:
        result = await session.execute(
            text(
                """
                UPDATE refresh_tokens
                SET revoked_at = NOW(),
                    expires_at = NOW()
                WHERE revoked_at IS NULL
                   OR expires_at > NOW()
                """
            )
        )
        await session.commit()
        return int(result.rowcount or 0)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Actually revoke tokens. Without this flag the command is a dry run.",
    )
    args = parser.parse_args()

    active_count = await _count_active_tokens()
    if not args.yes:
        print(f"Dry run: {active_count} active refresh token(s) would be revoked.")
        print("Re-run with --yes during the auth-hardening cutover to revoke them.")
        return

    updated_count = await _revoke_all_tokens()
    print(f"Revoked {updated_count} refresh token row(s).")


if __name__ == "__main__":
    asyncio.run(main())
