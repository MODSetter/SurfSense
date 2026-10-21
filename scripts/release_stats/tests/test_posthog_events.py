"""What reaches PostHog: personless aggregates, in batches the endpoint accepts."""

import json

from release_stats.posthog_capture import send_batches
from release_stats.posthog_events import DISTINCT_ID, snapshot_events
from tests.fake_http import FakeOpener


def snapshot(traffic=None):
    return {
        "taken_at": "2026-10-22T06:00:00Z",
        "repo": "acme/app",
        "assets": [
            {
                "tag": "v2.2.3",
                "asset": "SurfSense-arm64.zip",
                "kind": "update_zip_mac",
                "download_count": 4,
                "published_at": "2026-10-21T10:21:34Z",
                "prerelease": False,
            }
        ],
        "traffic": traffic,
        "traffic_skipped": None if traffic else "token cannot read traffic (403)",
    }


TRAFFIC = {
    "views": {
        "count": 120,
        "uniques": 40,
        "views": [
            {"timestamp": "2026-10-20T00:00:00Z", "count": 10, "uniques": 6},
            {"timestamp": "2026-10-21T00:00:00Z", "count": 12, "uniques": 7},
            {"timestamp": "2026-10-22T00:00:00Z", "count": 1, "uniques": 1},
        ],
    },
    "clones": {"count": 9, "uniques": 3, "clones": []},
    "referrers": [{"referrer": "news.ycombinator.com", "count": 8, "uniques": 5}],
    "paths": [
        {"path": "/acme/app/releases", "title": "Releases", "count": 3, "uniques": 2}
    ],
}


def test_each_asset_becomes_one_personless_event_with_its_count():
    [event] = snapshot_events(snapshot())

    assert event["event"] == "github_release_asset_snapshot"
    assert event["distinct_id"] == DISTINCT_ID
    assert event["timestamp"] == "2026-10-22T06:00:00Z"
    assert event["properties"] == {
        "tag": "v2.2.3",
        "asset": "SurfSense-arm64.zip",
        "kind": "update_zip_mac",
        "download_count": 4,
        "published_at": "2026-10-21T10:21:34Z",
        "$process_person_profile": False,
        "$geoip_disable": True,
    }


def test_no_traffic_event_is_sent_when_traffic_was_skipped():
    names = [event["event"] for event in snapshot_events(snapshot())]

    assert names == ["github_release_asset_snapshot"]


def test_the_traffic_event_carries_the_last_whole_day_beside_the_14_day_totals():
    traffic_event = snapshot_events(snapshot(TRAFFIC))[-1]
    properties = traffic_event["properties"]

    assert traffic_event["event"] == "github_traffic_snapshot"
    assert properties["day"] == "2026-10-21"
    assert (properties["day_views"], properties["day_view_uniques"]) == (12, 7)
    # A day GitHub left out had no traffic.
    assert (properties["day_clones"], properties["day_clone_uniques"]) == (0, 0)
    assert (properties["views_14d"], properties["clone_uniques_14d"]) == (120, 3)
    assert properties["referrers"] == [
        {"referrer": "news.ycombinator.com", "count": 8, "uniques": 5}
    ]
    assert properties["paths"] == [
        {"path": "/acme/app/releases", "count": 3, "uniques": 2}
    ]
    assert properties["$process_person_profile"] is False


def test_events_are_posted_in_batches_with_the_project_key():
    events = [{"event": "e", "distinct_id": DISTINCT_ID}] * 450
    opener = FakeOpener({})

    sent = send_batches(
        events, api_key="phc_test", host="https://eu.i.posthog.com/", opener=opener
    )

    bodies = [json.loads(request.data) for request in opener.requests]
    assert sent == 450
    assert [len(body["batch"]) for body in bodies] == [200, 200, 50]
    assert {body["api_key"] for body in bodies} == {"phc_test"}
    assert {request.full_url for request in opener.requests} == {
        "https://eu.i.posthog.com/batch/"
    }
