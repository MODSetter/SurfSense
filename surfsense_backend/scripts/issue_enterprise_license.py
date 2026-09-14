"""Issue a license from an invoice, without Stripe, and print its certificate.

Enterprise deals are invoiced, so there is no checkout session to fulfil. This
touches no database: Keygen is the system of record.

    python -m scripts.issue_enterprise_license --email ops@acme.com --seats 40
    python -m scripts.issue_enterprise_license --email cto@acme.com --plan individual

Pass --mail to also send it, which needs SMTP_ENABLED=TRUE.
"""

from __future__ import annotations

import argparse
import asyncio

from app.services.license_service import deliver_licenses, issue_license


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    parser.add_argument("--plan", choices=("individual", "team"), default="team")
    parser.add_argument("--seats", type=int, help="Required for --plan team")
    parser.add_argument(
        "--mail",
        action="store_true",
        help="Email the file as well as printing it",
    )
    args = parser.parse_args()

    if args.plan == "team":
        if args.seats is None or args.seats < 1:
            parser.error("--seats must be at least 1 for a team license")
    elif args.seats is not None:
        parser.error("--seats only applies to --plan team")

    issued = await issue_license(
        plan=args.plan,
        email=args.email,
        max_users=args.seats,
        source="enterprise",
    )
    if args.mail:
        await deliver_licenses(
            "purchase",
            to=issued.email,
            certificates=[issued.certificate],
            idempotency_key=issued.keygen_license_id,
        )
    print(issued.certificate, end="")


if __name__ == "__main__":
    asyncio.run(main())
