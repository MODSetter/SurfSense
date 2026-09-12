"""Issue a team license without Stripe and print its certificate."""

from __future__ import annotations

import argparse
import asyncio

from app.db import async_session_maker
from app.services.license_service import issue_license


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    parser.add_argument("--seats", required=True, type=int)
    args = parser.parse_args()
    if args.seats < 1:
        parser.error("--seats must be at least 1")

    async with async_session_maker() as session:
        purchase = await issue_license(
            session,
            plan="team",
            email=args.email,
            max_users=args.seats,
            source="enterprise",
        )
        await session.commit()
        print(purchase.certificate, end="")


if __name__ == "__main__":
    asyncio.run(main())
