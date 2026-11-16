"""The personless PostHog events a snapshot becomes.

Every number here is an aggregate GitHub already publishes or shows the repo's
maintainers; no event carries anything about a person.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from typing import Any

from .repo_traffic import Traffic
from .snapshot import Snapshot

# Personless events still need a distinct id; one constant keeps them off every
# person profile.
DISTINCT_ID = "github-release-stats"
_PERSONLESS = {"$process_person_profile": False, "$geoip_disable": True}

# The whole days inside GitHub's 14-day window under either reading of it
# (aligned to midnight, or rolling back 14 times 24 hours from now); the
# oldest bucket may be cut short, so it is never sent.
WHOLE_DAYS_RESENT = 13


def snapshot_events(snapshot: Snapshot) -> list[dict[str, Any]]:
    taken_at = snapshot["taken_at"]
    events = [
        _event(
            "github_release_asset_snapshot",
            taken_at,
            {
                "tag": row["tag"],
                "asset": row["asset"],
                "kind": row["kind"],
                "download_count": row["download_count"],
                "published_at": row["published_at"],
            },
        )
        for row in snapshot["assets"]
    ]
    traffic = snapshot["traffic"]
    if traffic is not None:
        events.append(
            _event("github_traffic_snapshot", taken_at, traffic_totals(traffic))
        )
        events.extend(traffic_day_events(snapshot))
    return events


def traffic_totals(traffic: Traffic) -> dict[str, Any]:
    """The 14-day totals and top lists; consecutive windows overlap, so never sum."""
    views, clones = traffic["views"], traffic["clones"]
    return {
        "views_14d": int(views.get("count") or 0),
        "view_uniques_14d": int(views.get("uniques") or 0),
        "clones_14d": int(clones.get("count") or 0),
        "clone_uniques_14d": int(clones.get("uniques") or 0),
        "referrers": [_counted(row, "referrer") for row in traffic["referrers"]],
        "paths": [_counted(row, "path") for row in traffic["paths"]],
    }


def traffic_day_events(snapshot: Snapshot) -> list[dict[str, Any]]:
    """One ``github_traffic_day`` per whole day GitHub still holds, keyed on the day.

    Every run resends the same days with the same uuid and timestamp, so
    PostHog keeps one copy of each day: a second run on one day replaces the
    first instead of adding to it, a missed run is filled in by the next, and a
    count GitHub was still settling is corrected the day after.
    """
    traffic = snapshot["traffic"]
    assert traffic is not None
    today = _date_of(snapshot["taken_at"])
    views = _by_day(traffic["views"].get("views"))
    clones = _by_day(traffic["clones"].get("clones"))
    events = []
    for days_ago in range(WHOLE_DAYS_RESENT, 0, -1):
        day = (today - timedelta(days=days_ago)).isoformat()
        day_views, day_clones = views.get(day, (0, 0)), clones.get(day, (0, 0))
        events.append(
            _event(
                "github_traffic_day",
                f"{day}T00:00:00Z",
                {
                    "day": day,
                    "views": day_views[0],
                    "view_uniques": day_views[1],
                    "clones": day_clones[0],
                    "clone_uniques": day_clones[1],
                },
                event_id=_day_event_id(snapshot["repo"], day),
            )
        )
    return events


def _event(
    name: str,
    timestamp: str,
    properties: dict[str, Any],
    *,
    event_id: str | None = None,
) -> dict[str, Any]:
    event = {
        "event": name,
        "distinct_id": DISTINCT_ID,
        "timestamp": timestamp,
        "properties": {**properties, **_PERSONLESS},
    }
    if event_id is not None:
        event["uuid"] = event_id
    return event


def _day_event_id(repo: str, day: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"github_traffic_day/{repo}/{day}"))


def _date_of(timestamp: str) -> date:
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00")).date()


def _by_day(buckets: list[dict[str, Any]] | None) -> dict[str, tuple[int, int]]:
    # GitHub leaves a day with no traffic out of the list.
    return {
        str(bucket.get("timestamp", ""))[:10]: (
            int(bucket.get("count") or 0),
            int(bucket.get("uniques") or 0),
        )
        for bucket in buckets or []
    }


def _counted(row: dict[str, Any], key: str) -> dict[str, Any]:
    return {
        key: row.get(key),
        "count": int(row.get("count") or 0),
        "uniques": int(row.get("uniques") or 0),
    }
