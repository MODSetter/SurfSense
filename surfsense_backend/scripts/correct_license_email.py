"""Repoint a license at the address its buyer actually owns, then resend it.

For the buyer who mistyped their email at checkout. The success page serves the
file regardless, so this only reaches someone who *also* closed the tab before
saving it -- rare, and handled by support rather than self-serve, because a
form that mails a license to an address you type would be a way to steal one.

Support matches on the **payment**, never on how similar two addresses look:
ask the buyer for the charge id (or last 4 + amount + date), find it in Stripe,
and use that checkout session id here.

Correcting the stored address matters as much as sending the file. Leave the
typo in Keygen and every future re-download is another support ticket, because
``/license/resend`` looks the customer up by that address.

    python -m scripts.correct_license_email --session cs_test_123 \
        --email real@buyer.com --mail

Prints the current record and asks for confirmation before writing, unless
--yes is passed.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from app.license.service import (
    LicenseNotFoundError,
    correct_license_email,
    deliver_licenses,
    find_license_by_checkout_session,
)


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--session",
        required=True,
        help="Stripe checkout session id, from the payment in the Stripe dashboard",
    )
    parser.add_argument("--email", required=True, help="The buyer's real address")
    parser.add_argument(
        "--mail",
        action="store_true",
        help="Also email the file to the corrected address",
    )
    parser.add_argument("--yes", action="store_true", help="Skip the confirmation")
    args = parser.parse_args()

    try:
        record = await find_license_by_checkout_session(args.session)
    except LicenseNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    current = record.metadata.get("email", "(none)")
    print(f"license   {record.keygen_license_id}")
    print(f"plan      {record.metadata.get('plan', '(none)')}")
    print(f"seats     {record.max_users if record.max_users is not None else '-'}")
    print(f"expiry    {record.expiry or 'per policy'}")
    print(f"email     {current}  ->  {args.email}")

    if current == args.email:
        print("\nnothing to do: the stored address already matches")
        return 0

    confirmed = args.yes or input(
        "\napply this correction? [y/N] "
    ).strip().lower() in {
        "y",
        "yes",
    }
    if not confirmed:
        print("aborted")
        return 1

    issued = await correct_license_email(record, args.email)
    print(f"\ncorrected. {issued.email} can now use /license/resend.")

    if args.mail:
        await deliver_licenses(
            "resend",
            to=issued.email,
            certificates=[issued.certificate],
            idempotency_key=f"correct:{issued.keygen_license_id}",
        )
        print("emailed the license file")
    else:
        print("\n--- certificate ---")
        print(issued.certificate, end="")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
