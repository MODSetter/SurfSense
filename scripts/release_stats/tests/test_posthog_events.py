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


def test_the_traffic_snapshot_carries_the_14_day_totals_and_top_lists():
    [traffic_event] = [
        event
        for event in snapshot_events(snapshot(TRAFFIC))
        if event["event"] == "github_traffic_snapshot"
    ]
    properties = traffic_event["properties"]

    assert traffic_event["timestamp"] == "2026-10-22T06:00:00Z"
    assert (properties["views_14d"], properties["clone_uniques_14d"]) == (120, 3)
    assert properties["referrers"] == [
        {"referrer": "news.ycombinator.com", "count": 8, "uniques": 5}
    ]
    assert properties["paths"] == [
        {"path": "/acme/app/releases", "count": 3, "uniques": 2}
    ]
    assert properties["$process_person_profile"] is False


def day_events(taken_at="2026-10-22T06:00:00Z", repo="acme/app"):
    taken = {**snapshot(TRAFFIC), "taken_at": taken_at, "repo": repo}
    return {
        event["properties"]["day"]: event
        for event in snapshot_events(taken)
        if event["event"] == "github_traffic_day"
    }


def test_every_whole_day_still_held_is_sent_at_its_own_midnight():
    days = day_events()

    assert list(days) == [f"2026-10-{n:02d}" for n in range(9, 22)]
    yesterday = days["2026-10-21"]
    assert yesterday["timestamp"] == "2026-10-21T00:00:00Z"
    assert yesterday["distinct_id"] == DISTINCT_ID
    assert yesterday["properties"] == {
        "day": "2026-10-21",
        "views": 12,
        "view_uniques": 7,
        # A day GitHub left out had no traffic.
        "clones": 0,
        "clone_uniques": 0,
        "$process_person_profile": False,
        "$geoip_disable": True,
    }


def test_a_rerun_or_a_later_run_sends_each_day_under_the_same_identity():
    first = day_events("2026-10-22T06:00:00Z")
    rerun = day_events("2026-10-22T09:41:07Z")
    next_day = day_events("2026-10-23T06:00:00Z")

    for day in ("2026-10-20", "2026-10-21"):
        identity = (first[day]["uuid"], first[day]["timestamp"])
        assert (rerun[day]["uuid"], rerun[day]["timestamp"]) == identity
        assert (next_day[day]["uuid"], next_day[day]["timestamp"]) == identity
    assert first["2026-10-20"]["uuid"] != first["2026-10-21"]["uuid"]
    other_repo = day_events(repo="acme/other")
    assert other_repo["2026-10-21"]["uuid"] != first["2026-10-21"]["uuid"]


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
