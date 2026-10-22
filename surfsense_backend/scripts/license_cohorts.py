"""Print weekly trial cohorts: business share, plugin use, conversion, refunds.

    python -m scripts.license_cohorts
    python -m scripts.license_cohorts --posthog

Reads every Keygen licence; Stripe when ``STRIPE_SECRET_KEY`` is set (a
restricted read-only key is enough); the plugin host when
``PLUGIN_HOST_ADMIN_URL`` and ``USAGE_ADMIN_TOKEN`` are set. Prints aggregates
only, with cells under 5 as "<5". ``--posthog`` also sends one personless
``license_cohort_weekly`` event per week through ``POSTHOG_API_KEY``.

Never act on a single row of this, such as mailing a lapsed trial: the
addresses were given to receive a licence, not for outreach.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import UTC, datetime

from app.config import config
from app.license.cohorts.keygen_licences import read_licences
from app.license.cohorts.markdown_table import LEGEND, render_table
from app.license.cohorts.plugin_host_first_seen import read_first_seen
from app.license.cohorts.posthog_events import send_cohort_events
from app.license.cohorts.published_figures import SMALLEST_SHOWN
from app.license.cohorts.stripe_purchases import add_stripe_view
from app.license.cohorts.weekly import weekly_cohorts
from app.observability.analytics import posthog as ph_analytics


def _stripe_client():
    from stripe import StripeClient

    return StripeClient(config.STRIPE_SECRET_KEY)


async def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="license_cohorts")
    parser.add_argument(
        "--posthog",
        action="store_true",
        help="also send one personless event per week to PostHog",
    )
    args = parser.parse_args(argv)

    if args.posthog and not ph_analytics.is_enabled():
        print("error: --posthog needs POSTHOG_API_KEY", file=sys.stderr)
        return 2

    trials, purchases = await read_licences()
    read = len(trials) + len(purchases)
    sources = [f"Keygen: {read if read >= SMALLEST_SHOWN else '<5'} licences read"]

    if config.STRIPE_SECRET_KEY:
        failed = add_stripe_view(purchases, _stripe_client())
        sources.append(f"Stripe: read, {failed} lookups failed")
    else:
        sources.append("Stripe: not configured, refunds from Keygen suspensions")

    first_seen = None
    admin_url = os.environ.get("PLUGIN_HOST_ADMIN_URL")
    admin_token = os.environ.get("USAGE_ADMIN_TOKEN")
    if admin_url and admin_token:
        first_seen = await read_first_seen(admin_url, admin_token)
        sources.append("Plugin host: read")
    else:
        sources.append("Plugin host: not configured")

    today = datetime.now(UTC).date()
    cohorts = weekly_cohorts(trials, purchases, first_seen)
    print(f"# Trial cohorts by ISO week, as of {today.isoformat()}\n")
    print(render_table(cohorts, today))
    print(f"\n{LEGEND}\n")
    for source in sources:
        print(f"- {source}")

    if args.posthog:
        sent = send_cohort_events(cohorts, today)
        ph_analytics.shutdown()
        print(f"\nsent {sent} {'event' if sent == 1 else 'events'} to PostHog")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
