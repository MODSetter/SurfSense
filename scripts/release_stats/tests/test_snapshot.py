"""A snapshot reads every page of releases, and keeps going without traffic access."""

import re
from datetime import UTC, datetime

import pytest

from release_stats.github_api import GitHubApi, GitHubOriginError, next_page_url
from release_stats.snapshot import take_snapshot
from tests.fake_http import FakeOpener, LocalServer

API = "https://api.github.com"
REPO = "acme/app"
RELEASES = f"{API}/repos/{REPO}/releases?per_page=100"
PAGE_2 = f"{API}/repositories/1/releases?per_page=100&page=2"
NOW = datetime(2026, 10, 22, 6, 0, tzinfo=UTC)

TRAFFIC = {
    f"{API}/repos/{REPO}/traffic/views": (
        {"count": 30, "uniques": 9, "views": []},
        None,
    ),
    f"{API}/repos/{REPO}/traffic/clones": (
        {"count": 4, "uniques": 2, "clones": []},
        None,
    ),
    f"{API}/repos/{REPO}/traffic/popular/referrers": (
        [{"referrer": "google.com", "count": 5, "uniques": 3}],
        None,
    ),
    f"{API}/repos/{REPO}/traffic/popular/paths": (
        [{"path": "/acme/app", "title": "app", "count": 7, "uniques": 4}],
        None,
    ),
}


def release(tag, assets, *, draft=False, prerelease=False):
    return {
        "tag_name": tag,
        "draft": draft,
        "prerelease": prerelease,
        "published_at": None if draft else "2026-10-21T10:21:34Z",
        "assets": [{"name": name, "download_count": n} for name, n in assets],
    }


def releases_over_two_pages():
    return {
        RELEASES: (
            [release("v2.2.3", [("SurfSense-Setup.exe", 50), ("stable.yml", 22)])],
            f'<{PAGE_2}>; rel="next", <{PAGE_2}>; rel="last"',
        ),
        PAGE_2: ([release("v0.0.40", [("latest.yml", 2481)])], None),
    }


def test_every_page_of_releases_is_read_into_flat_rows():
    opener = FakeOpener({**releases_over_two_pages(), **TRAFFIC})

    snapshot = take_snapshot(GitHubApi("t", opener=opener), REPO, NOW)

    assert [
        (r["tag"], r["asset"], r["kind"], r["download_count"])
        for r in snapshot["assets"]
    ] == [
        ("v2.2.3", "SurfSense-Setup.exe", "installer_windows", 50),
        ("v2.2.3", "stable.yml", "manifest_stable_windows", 22),
        ("v0.0.40", "latest.yml", "manifest_legacy_windows", 2481),
    ]
    assert snapshot["assets"][0]["published_at"] == "2026-10-21T10:21:34Z"
    assert snapshot["taken_at"] == "2026-10-22T06:00:00Z"


def test_a_draft_release_is_left_out():
    opener = FakeOpener(
        {
            RELEASES: (
                [release("v2.2.4", [("SurfSense-Setup.exe", 3)], draft=True)],
                None,
            ),
            **TRAFFIC,
        }
    )

    assert take_snapshot(GitHubApi("t", opener=opener), REPO, NOW)["assets"] == []


def test_traffic_is_kept_when_the_token_may_read_it():
    opener = FakeOpener({**releases_over_two_pages(), **TRAFFIC})

    snapshot = take_snapshot(GitHubApi("t", opener=opener), REPO, NOW)

    assert snapshot["traffic"]["views"]["count"] == 30
    assert snapshot["traffic"]["referrers"][0]["referrer"] == "google.com"
    assert snapshot["traffic_skipped"] is None


def test_a_token_without_push_access_skips_traffic_but_keeps_the_counts():
    denied = dict.fromkeys(TRAFFIC, 403)
    opener = FakeOpener({**releases_over_two_pages(), **denied})

    snapshot = take_snapshot(GitHubApi("t", opener=opener), REPO, NOW)

    assert snapshot["traffic"] is None
    assert "403" in snapshot["traffic_skipped"]
    assert len(snapshot["assets"]) == 3


def test_the_token_is_sent_as_a_bearer_and_none_is_sent_without_one():
    with_token = FakeOpener(releases_over_two_pages())
    GitHubApi("secret", opener=with_token).get("repos/acme/app/releases?per_page=100")
    without = FakeOpener(releases_over_two_pages())
    GitHubApi(None, opener=without).get("repos/acme/app/releases?per_page=100")

    assert with_token.requests[0].get_header("Authorization") == "Bearer secret"
    assert without.requests[0].get_header("Authorization") is None


def test_only_a_next_link_continues_the_pages():
    assert next_page_url(f'<{PAGE_2}>; rel="next"') == PAGE_2
    assert next_page_url(f'<{RELEASES}>; rel="prev", <{RELEASES}>; rel="first"') is None
    assert next_page_url(None) is None


def test_a_next_link_on_the_api_origin_is_followed_with_the_token():
    opener = FakeOpener(releases_over_two_pages())

    pages = list(GitHubApi("secret", opener=opener).pages(RELEASES))

    assert len(pages) == 2
    assert [request.full_url for request in opener.requests] == [RELEASES, PAGE_2]
    assert opener.requests[1].get_header("Authorization") == "Bearer secret"


@pytest.mark.parametrize(
    "elsewhere",
    [
        "https://collector.example/releases?page=2",
        "http://api.github.com/repositories/1/releases?page=2",
        "https://api.github.com.collector.example/releases?page=2",
        "https://api.github.com@collector.example/releases?page=2",
    ],
)
def test_a_next_link_off_the_api_origin_stops_paging_before_the_token_leaves(
    elsewhere,
):
    opener = FakeOpener(
        {RELEASES: ([release("v2.2.3", [])], f'<{elsewhere}>; rel="next"')}
    )
    pages = GitHubApi("secret", opener=opener).pages(RELEASES)

    assert next(pages) == [release("v2.2.3", [])]
    with pytest.raises(GitHubOriginError, match=re.escape(API)):
        next(pages)
    assert [request.full_url for request in opener.requests] == [RELEASES]


def test_a_redirect_off_the_api_origin_is_not_followed_with_the_token():
    # urllib copies every header onto a redirect, the Authorization one too.
    with LocalServer() as api, LocalServer() as elsewhere:
        api.redirects["/repos/acme/app/releases"] = f"{elsewhere.url}/collect"

        with pytest.raises(GitHubOriginError, match=re.escape(api.url)):
            list(GitHubApi("secret", root=api.url).pages("repos/acme/app/releases"))

        assert elsewhere.seen == []


def test_a_redirect_on_the_api_origin_is_followed_with_the_token():
    with LocalServer() as api:
        api.redirects["/repos/acme/app/releases"] = f"{api.url}/repositories/1/releases"

        pages = list(GitHubApi("secret", root=api.url).pages("repos/acme/app/releases"))

        assert pages == [[]]
        assert api.seen == [
            ("/repos/acme/app/releases", "Bearer secret"),
            ("/repositories/1/releases", "Bearer secret"),
        ]
