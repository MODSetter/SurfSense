"""A day's usage, with no license id in it, sent to PostHog as personless events.

By hand, from backend/plugins/: python -m host.usage_meter.rollup --day YYYY-MM-DD
"""

import argparse
import json
import logging
import uuid
from dataclasses import asdict, dataclass
from typing import Any

import anyio
import httpx2

from host.usage_meter.meter_settings import MeterSettings
from host.usage_meter.usage_store import DailyUsage, UsageStore
from host.usage_meter.utc_days import is_day

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 30.0
# Personless events still need a distinct id; this one names the sender, not a person.
DISTINCT_ID = "surfsense-plugin-host"
# Fixed, so a day sent again carries the same event ids and PostHog replaces the earlier copy.
EVENT_ID_NAMESPACE = uuid.uuid5(
    uuid.NAMESPACE_URL, "https://plugins.surfsense.com/usage"
)


@dataclass(frozen=True)
class PostHogRollup:
    api_key: str
    host: str

    async def send(self, usage: DailyUsage) -> None:
        async with httpx2.AsyncClient(timeout=TIMEOUT_SECONDS) as http:
            response = await http.post(
                f"{self.host.rstrip('/')}/batch/",
                json={"api_key": self.api_key, "batch": rollup_events(usage)},
            )
            response.raise_for_status()


def rollup_events(usage: DailyUsage) -> list[dict[str, Any]]:
    """One `plugin_usage_daily` per plugin, tool and outcome, and one `plugin_licences_daily`."""
    tools = [
        _event(
            "plugin_usage_daily",
            usage.day,
            asdict(tool),
            key=(tool.plugin, tool.tool, tool.outcome),
        )
        for tool in usage.tools
    ]
    licences = _event(
        "plugin_licences_daily",
        usage.day,
        {
            "active_licences": usage.active_licences,
            "new_licences": usage.new_licences,
        },
    )
    return [*tools, licences]


def _event(
    name: str, day: str, properties: dict[str, Any], key: tuple[str, ...] = ()
) -> dict[str, Any]:
    return {
        "uuid": str(uuid.uuid5(EVENT_ID_NAMESPACE, json.dumps([name, day, *key]))),
        "event": name,
        "distinct_id": DISTINCT_ID,
        # Midday UTC, so a project in another time zone still shows it on its day.
        "timestamp": f"{day}T12:00:00Z",
        "properties": {
            "day": day,
            **properties,
            # No person profile, and no location looked up from the host's address.
            "$process_person_profile": False,
            "$geoip_disable": True,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m host.usage_meter.rollup",
        description="Send one UTC day's plugin usage to PostHog, with no license ids.",
    )
    parser.add_argument("--day", required=True, help="the UTC day, YYYY-MM-DD")
    args = parser.parse_args(argv)
    if not is_day(args.day):
        parser.error("--day must be a date written YYYY-MM-DD")
    settings = MeterSettings.from_env()
    if not settings.posthog_api_key:
        parser.error("POSTHOG_API_KEY is not set")
    if not settings.db_path.is_file():
        parser.error(f"no usage file at {settings.db_path} (USAGE_DB_PATH)")
    store = UsageStore(settings.db_path)
    usage = store.daily_usage(args.day)
    anyio.run(
        PostHogRollup(settings.posthog_api_key, settings.posthog_host).send, usage
    )
    store.mark_rollup_sent(args.day)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger.info("Sent %s: %d plugin_usage_daily events", args.day, len(usage.tools))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
