"""The personless PostHog events a snapshot becomes.

Every number here is an aggregate GitHub already publishes or shows the repo's
maintainers; no event carries anything about a person.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from .snapshot import Snapshot

# Personless events still need a distinct id; one constant keeps them off every
# person profile.
DISTINCT_ID = "github-release-stats"
_PERSONLESS = {"$process_person_profile": False, "$geoip_disable": True}


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
    if snapshot["traffic"] is not None:
        events.append(
            _event(
                "github_traffic_snapshot",
                taken_at,
                traffic_properties(snapshot, _day_before(taken_at)),
            )
        )
    return events


def traffic_properties(snapshot: Snapshot, day: date) -> dict[str, Any]:
    """The 14-day totals, plus ``day``'s own numbers for a lasting daily series.

    The 14-day windows of consecutive snapshots overlap, so only ``day_*`` may
    be summed across days.
    """
    traffic = snapshot["traffic"]
    assert traffic is not None
    views, clones = traffic["views"], traffic["clones"]
    day_views = _bucket(views.get("views"), day)
    day_clones = _bucket(clones.get("clones"), day)
    return {
        "day": day.isoformat(),
        "day_views": day_views["count"],
        "day_view_uniques": day_views["uniques"],
        "day_clones": day_clones["count"],
        "day_clone_uniques": day_clones["uniques"],
        "views_14d": int(views.get("count") or 0),
        "view_uniques_14d": int(views.get("uniques") or 0),
        "clones_14d": int(clones.get("count") or 0),
        "clone_uniques_14d": int(clones.get("uniques") or 0),
        "referrers": [_counted(row, "referrer") for row in traffic["referrers"]],
        "paths": [_counted(row, "path") for row in traffic["paths"]],
    }


def _event(name: str, timestamp: str, properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "event": name,
        "distinct_id": DISTINCT_ID,
        "timestamp": timestamp,
        "properties": {**properties, **_PERSONLESS},
    }


def _day_before(timestamp: str) -> date:
    taken = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    return taken.date() - timedelta(days=1)


def _bucket(buckets: list[dict[str, Any]] | None, day: date) -> dict[str, int]:
    # GitHub leaves a day with no traffic out of the list.
    for bucket in buckets or []:
        if str(bucket.get("timestamp", "")).startswith(day.isoformat()):
            return {
                "count": int(bucket.get("count") or 0),
                "uniques": int(bucket.get("uniques") or 0),
            }
    return {"count": 0, "uniques": 0}


def _counted(row: dict[str, Any], key: str) -> dict[str, Any]:
    return {
        key: row.get(key),
        "count": int(row.get("count") or 0),
        "uniques": int(row.get("uniques") or 0),
    }
