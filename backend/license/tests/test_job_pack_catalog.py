"""The packs the route may serve: read from the store at most once per TTL, each release
downloaded and checked once, and the last good packs kept while the store fails.

GitHub is faked at its transport, so the store's client runs as written.
"""

from __future__ import annotations

import asyncio
import logging
import zipfile
from pathlib import Path

import pytest

from license.job_packs import catalog, github_releases
from license.job_packs.catalog import (
    PackCatalog,
    PackSourceUnavailableError,
    configured_source,
    shared_catalog,
)
from license.job_packs.directory import DirectorySource
from license.job_packs.github_releases import GitHubReleases
from license.job_packs.source import PackAsset
from license.job_packs.verify import MAX_PACK_BYTES, PublishedPack
from license.settings import config
from license.tests.github_fake import FakeGitHub
from license.tests.job_pack_samples import (
    corrupt_member,
    pack_zip,
    with_name_bytes,
    write_pack,
)

pytestmark = pytest.mark.unit

TTL = 600.0


class Clock:
    def __init__(self) -> None:
        self.now = 1_000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock() -> Clock:
    return Clock()


def store_of(github: FakeGitHub) -> GitHubReleases:
    return GitHubReleases(github.repo, github.token)


def served(packs: tuple[PublishedPack, ...]) -> list[tuple[str, str]]:
    return sorted((pack.id, pack.version) for pack in packs)


def publish(
    github: FakeGitHub,
    version: str = "1.0.0",
    *,
    pack_id: str = "sample-jobs",
    data: bytes | None = None,
    **kw,
) -> int:
    """A release as the publisher makes one: `<id>-v<version>`, one `<id>-<version>.zip`."""
    if data is None:
        data = pack_zip(pack_id=pack_id, version=version)
    return github.publish(
        f"{pack_id}-v{version}", f"{pack_id}-{version}.zip", data, **kw
    )


@pytest.fixture
def releases(trusted_pack_key, github: FakeGitHub, clock: Clock) -> PackCatalog:
    return PackCatalog(store_of(github), ttl_seconds=TTL, clock=clock)


# reading ----------------------------------------------------------------------


async def test_the_store_is_listed_once_per_ttl(
    releases: PackCatalog, github: FakeGitHub, clock: Clock
) -> None:
    publish(github)

    first = await releases.packs()
    clock.advance(TTL - 1)
    again = await releases.packs()
    clock.advance(1)
    await releases.packs()

    assert served(first) == served(again) == [("sample-jobs", "1.0.0")]
    assert len(github.listings()) == 2


async def test_each_release_is_downloaded_once_and_kept(
    releases: PackCatalog, github: FakeGitHub, clock: Clock
) -> None:
    publish(github)

    await releases.packs()
    clock.advance(TTL)
    packs = await releases.packs()

    assert served(packs) == [("sample-jobs", "1.0.0")]
    assert len(github.listings()) == 2
    assert len(github.downloads()) == len(github.fetched()) == 1


async def test_requests_arriving_together_share_one_read(
    releases: PackCatalog, github: FakeGitHub
) -> None:
    publish(github)

    answers = await asyncio.gather(*(releases.packs() for _ in range(5)))

    assert {served(packs)[0] for packs in answers} == {("sample-jobs", "1.0.0")}
    assert len(github.listings()) == 1
    assert len(github.downloads()) == 1


async def test_every_page_of_releases_is_read(
    releases: PackCatalog, github: FakeGitHub
) -> None:
    github.page_size = 2
    for version in ("1.0.0", "1.1.0", "1.2.0"):
        publish(github, version)

    packs = await releases.packs()

    assert [version for _, version in served(packs)] == ["1.0.0", "1.1.0", "1.2.0"]
    assert [r.url.params.get("page") for r in github.listings()] == [None, "2"]


async def test_github_is_asked_as_its_api_documents(
    releases: PackCatalog, github: FakeGitHub
) -> None:
    publish(github)

    await releases.packs()

    (listing,) = github.listings()
    (download,) = github.downloads()
    assert listing.url.params["per_page"] == "100"
    assert listing.headers["accept"] == "application/vnd.github+json"
    assert download.headers["accept"] == "application/octet-stream"
    for request in (listing, download):
        assert request.headers["x-github-api-version"] == "2022-11-28"
        assert request.headers["user-agent"] == "SurfSense-license-server"
        assert request.headers["authorization"] == f"Bearer {github.token}"


async def test_the_assets_redirect_is_followed_without_the_token(
    releases: PackCatalog, github: FakeGitHub
) -> None:
    """The storage's signed URL is its own credential; the token must not travel there."""
    publish(github)

    packs = await releases.packs()

    (fetch,) = github.fetched()
    assert served(packs) == [("sample-jobs", "1.0.0")]
    assert fetch.url.scheme == "https"
    assert "authorization" not in fetch.headers
    assert fetch.headers["user-agent"] == "SurfSense-license-server"


async def test_a_redirect_to_plain_http_is_refused_and_tried_again_in_a_minute(
    releases: PackCatalog, github: FakeGitHub, clock: Clock
) -> None:
    publish(github)
    github.redirect_scheme = "http"

    refused = await releases.packs()
    github.redirect_scheme = "https"
    clock.advance(catalog.RETRY_SECONDS)
    retried = await releases.packs()

    assert served(refused) == []
    assert served(retried) == [("sample-jobs", "1.0.0")]
    (fetch,) = github.fetched()
    assert fetch.url.scheme == "https"


async def test_a_next_page_outside_githubs_api_is_never_asked(
    releases: PackCatalog, github: FakeGitHub, caplog: pytest.LogCaptureFixture
) -> None:
    """Every page is asked with the token, so a page elsewhere fails the read instead."""
    publish(github)
    github.next_link = "https://pages.example.com/releases?page=2"

    with caplog.at_level(logging.ERROR), pytest.raises(PackSourceUnavailableError):
        await releases.packs()

    assert "outside its API" in caplog.text
    assert [request.url.host for request in github.requests] == ["api.github.com"]


async def test_an_asset_described_outside_githubs_api_is_skipped_and_never_asked(
    releases: PackCatalog, github: FakeGitHub, caplog: pytest.LogCaptureFixture
) -> None:
    """Its download would be asked with the token, so the release is passed over."""
    publish(github, "1.0.0")
    publish(github, "1.1.0", url="https://assets.example.com/2")

    with caplog.at_level(logging.WARNING):
        packs = await releases.packs()

    assert served(packs) == [("sample-jobs", "1.0.0")]
    assert "sample-jobs-v1.1.0" in caplog.text
    assert "assets.example.com" not in {request.url.host for request in github.requests}


async def test_the_stores_client_follows_no_redirect_by_itself() -> None:
    """It takes the asset's redirect itself, without the token; a client following one on
    its own would carry the token to the storage."""
    async with github_releases._http() as client:
        assert client.follow_redirects is False


async def test_drafts_prereleases_foreign_tags_and_misnamed_assets_are_skipped(
    releases: PackCatalog, github: FakeGitHub, caplog: pytest.LogCaptureFixture
) -> None:
    publish(github, "1.0.0")
    publish(github, "1.1.0", draft=True)
    publish(github, "1.2.0", prerelease=True)
    publish(github, "1.3.0", state="open")
    github.publish("notes", "notes.zip", pack_zip())
    github.publish("sample-jobs-v1.4.0", "sample-jobs-1.4.zip", pack_zip())
    # Digits other than 0 to 9 are no version: no header could carry one.
    other_digits = "1.0.\u0661"
    github.publish(
        f"sample-jobs-v{other_digits}",
        f"sample-jobs-{other_digits}.zip",
        pack_zip(version=other_digits),
    )

    with caplog.at_level(logging.WARNING):
        packs = await releases.packs()

    assert served(packs) == [("sample-jobs", "1.0.0")]
    assert len(github.downloads()) == 1
    assert "notes" in caplog.text
    assert "sample-jobs-v1.4.0" in caplog.text
    assert f"sample-jobs-v{other_digits}" in caplog.text


async def test_a_release_failing_its_checks_is_never_served_and_the_previous_one_is(
    releases: PackCatalog,
    github: FakeGitHub,
    clock: Clock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    publish(github, "1.0.0")
    await releases.packs()
    publish(github, "1.1.0", data=pack_zip(version="1.1.0", keys=()))
    clock.advance(TTL)

    with caplog.at_level(logging.ERROR):
        packs = await releases.packs()
    clock.advance(TTL)
    await releases.packs()

    assert served(packs) == [("sample-jobs", "1.0.0")]
    assert "sample-jobs-1.1.0.zip" in caplog.text
    assert "PACK_NOT_SIGNED" in caplog.text
    # Refused once, never fetched again: a published asset never changes.
    assert len(github.downloads()) == 2


async def test_a_release_that_cannot_be_read_never_takes_the_others_down(
    releases: PackCatalog,
    github: FakeGitHub,
    clock: Clock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    deflated = pack_zip(version="1.1.0", compression=zipfile.ZIP_DEFLATED)
    misnamed = pack_zip(version="1.2.0", extra_members=(("café.txt", b"x"),))
    publish(github, "1.0.0")
    publish(github, "1.1.0", data=corrupt_member(deflated, "LICENSE.txt"))
    publish(
        github, "1.2.0", data=with_name_bytes(misnamed, "café.txt", b"caf\xff\xfe.txt")
    )

    with caplog.at_level(logging.ERROR):
        packs = await releases.packs()
    clock.advance(catalog.RETRY_SECONDS)
    await releases.packs()
    clock.advance(TTL)
    await releases.packs()

    assert served(packs) == [("sample-jobs", "1.0.0")]
    for name in ("sample-jobs-1.1.0.zip", "sample-jobs-1.2.0.zip"):
        assert f"Job pack {name} is refused, NOT_A_PACK" in caplog.text
    # A refusal is not a failed read: the next listing waits for the TTL.
    assert len(github.listings()) == 2
    assert len(github.downloads()) == 3


async def test_a_download_failing_with_an_unexpected_error_refuses_only_that_release(
    trusted_pack_key, tmp_path: Path, clock: Clock, caplog: pytest.LogCaptureFixture
) -> None:
    write_pack(tmp_path, version="1.0.0")
    write_pack(tmp_path, version="1.1.0")

    class Unreadable(DirectorySource):
        async def read(self, asset: PackAsset) -> bytes:
            if asset.name.endswith("1.1.0.zip"):
                raise LookupError("a bug in the store")
            return await super().read(asset)

    packs = PackCatalog(Unreadable(tmp_path), ttl_seconds=TTL, clock=clock)
    with caplog.at_level(logging.ERROR):
        served_packs = await packs.packs()

    assert served(served_packs) == [("sample-jobs", "1.0.0")]
    assert "LookupError" in caplog.text


async def test_an_unexpected_error_keeps_the_last_good_packs(
    trusted_pack_key, tmp_path: Path, clock: Clock, caplog: pytest.LogCaptureFixture
) -> None:
    write_pack(tmp_path)

    class Breaking(DirectorySource):
        broken = False
        listed = 0

        async def assets(self) -> list[PackAsset]:
            type(self).listed += 1
            if self.broken:
                raise KeyError("tag_name")
            return await super().assets()

    store = Breaking(tmp_path)
    packs = PackCatalog(store, ttl_seconds=TTL, clock=clock)
    await packs.packs()
    Breaking.broken = True
    clock.advance(TTL)

    with caplog.at_level(logging.ERROR):
        kept = await packs.packs()
    clock.advance(catalog.RETRY_SECONDS - 1)
    await packs.packs()

    assert served(kept) == [("sample-jobs", "1.0.0")]
    assert "KeyError" in caplog.text
    assert Breaking.listed == 2


async def test_the_read_has_a_deadline_and_keeps_the_last_good_packs(
    trusted_pack_key,
    tmp_path: Path,
    clock: Clock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_pack(tmp_path)

    class Stalling(DirectorySource):
        stalled = False

        async def assets(self) -> list[PackAsset]:
            if self.stalled:
                await asyncio.sleep(5)
            return await super().assets()

    packs = PackCatalog(Stalling(tmp_path), ttl_seconds=TTL, clock=clock)
    await packs.packs()
    Stalling.stalled = True
    monkeypatch.setattr(catalog, "READ_DEADLINE_SECONDS", 0.05)
    clock.advance(TTL)

    kept = await asyncio.wait_for(packs.packs(), timeout=2)

    assert served(kept) == [("sample-jobs", "1.0.0")]


async def test_a_check_past_its_deadline_refuses_only_that_release(
    releases: PackCatalog,
    github: FakeGitHub,
    clock: Clock,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A zip too slow to check is refused as a broken one is: the read goes on, and the
    release is never checked again, so it holds back no newer one."""
    deadline = catalog.CHECK_DEADLINE_SECONDS
    publish(github, "1.0.0")
    await releases.packs()
    publish(github, "1.1.0")
    clock.advance(TTL)
    # No check ends in no time, so this one is past its deadline.
    monkeypatch.setattr(catalog, "CHECK_DEADLINE_SECONDS", 0)

    with caplog.at_level(logging.ERROR):
        kept = await releases.packs()
    monkeypatch.setattr(catalog, "CHECK_DEADLINE_SECONDS", deadline)
    clock.advance(catalog.RETRY_SECONDS)
    await releases.packs()
    publish(github, "1.2.0")
    clock.advance(TTL)
    newer = await releases.packs()

    assert served(kept) == [("sample-jobs", "1.0.0")]
    assert "sample-jobs-1.1.0.zip took over 0 s to check" in caplog.text
    # Not a failed read: the next listing waited for the TTL, not a minute.
    assert len(github.listings()) == 3
    assert served(newer) == [("sample-jobs", "1.0.0"), ("sample-jobs", "1.2.0")]
    assert len(github.downloads()) == 3


@pytest.mark.parametrize("chunked", [True, False], ids=["streamed", "with a length"])
async def test_a_download_past_50_mb_is_cut_off_and_never_tried_again(
    releases: PackCatalog,
    github: FakeGitHub,
    clock: Clock,
    caplog: pytest.LogCaptureFixture,
    chunked: bool,
) -> None:
    """Listed small, sent large: the body is stopped at the cap, and the release refused."""
    publish(github, "1.0.0")
    oversized = publish(github, "1.1.0", data=bytes(MAX_PACK_BYTES + 1), size=1_000)
    if chunked:
        github.chunked.add(oversized)

    with caplog.at_level(logging.ERROR):
        packs = await releases.packs()
    clock.advance(TTL)
    await releases.packs()

    assert served(packs) == [("sample-jobs", "1.0.0")]
    assert "Job pack sample-jobs-1.1.0.zip is refused, PACK_TOO_LARGE" in caplog.text
    assert len(github.downloads()) == 2


async def test_an_asset_listed_over_50_mb_is_never_downloaded(
    releases: PackCatalog, github: FakeGitHub, caplog: pytest.LogCaptureFixture
) -> None:
    publish(github, "1.0.0", size=MAX_PACK_BYTES + 1)

    with caplog.at_level(logging.ERROR):
        packs = await releases.packs()

    assert served(packs) == []
    assert github.downloads() == []
    assert "sample-jobs-1.0.0.zip" in caplog.text


# failing ----------------------------------------------------------------------


async def test_github_failing_keeps_the_last_good_packs_and_retries_after_a_minute(
    releases: PackCatalog,
    github: FakeGitHub,
    clock: Clock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    publish(github)
    await releases.packs()
    github.down = True
    clock.advance(TTL)

    with caplog.at_level(logging.ERROR):
        kept = await releases.packs()
    asked = len(github.requests)
    clock.advance(catalog.RETRY_SECONDS - 1)
    await releases.packs()
    waited = len(github.requests)
    clock.advance(1)
    await releases.packs()

    assert served(kept) == [("sample-jobs", "1.0.0")]
    assert "last good" in caplog.text
    assert waited == asked
    assert len(github.requests) == asked + 1


async def test_a_cold_start_while_github_fails_is_unavailable(
    releases: PackCatalog,
    github: FakeGitHub,
    clock: Clock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    publish(github)
    github.down = True

    with caplog.at_level(logging.ERROR), pytest.raises(PackSourceUnavailableError):
        await releases.packs()
    with pytest.raises(PackSourceUnavailableError):
        await releases.packs()
    github.down = False
    clock.advance(catalog.RETRY_SECONDS)
    packs = await releases.packs()

    assert "none" in caplog.text
    assert len(github.listings()) == 2
    assert served(packs) == [("sample-jobs", "1.0.0")]


@pytest.mark.parametrize(
    ("status", "headers", "said"),
    [
        (401, {}, "GitHub refused JOB_PACKS_GITHUB_TOKEN"),
        (
            403,
            {"x-ratelimit-remaining": "0", "x-ratelimit-reset": "1793750400"},
            "rate limit",
        ),
        (403, {}, "does not exist, or the token cannot read it"),
        (404, {}, "does not exist, or the token cannot read it"),
        (500, {}, "GitHub answered 500"),
    ],
)
async def test_a_refused_listing_is_logged_without_the_token(
    releases: PackCatalog,
    github: FakeGitHub,
    caplog: pytest.LogCaptureFixture,
    status: int,
    headers: dict[str, str],
    said: str,
) -> None:
    github.status = status
    github.status_headers = headers

    with caplog.at_level(logging.DEBUG), pytest.raises(PackSourceUnavailableError):
        await releases.packs()

    assert said in caplog.text
    assert github.token not in caplog.text


async def test_a_failed_new_download_is_retried_after_a_minute(
    releases: PackCatalog, github: FakeGitHub, clock: Clock
) -> None:
    asset = publish(github)
    github.asset_status[asset] = 502

    failed = await releases.packs()
    del github.asset_status[asset]
    clock.advance(catalog.RETRY_SECONDS - 1)
    still = await releases.packs()
    clock.advance(1)
    retried = await releases.packs()

    assert served(failed) == served(still) == []
    assert served(retried) == [("sample-jobs", "1.0.0")]


async def test_a_deleted_release_stops_being_served(
    releases: PackCatalog, github: FakeGitHub, clock: Clock
) -> None:
    publish(github, "1.0.0")
    publish(github, "1.1.0")
    before = await releases.packs()
    github.unpublish("sample-jobs-v1.1.0")
    clock.advance(TTL)

    after = await releases.packs()

    assert [version for _, version in served(before)] == ["1.0.0", "1.1.0"]
    assert served(after) == [("sample-jobs", "1.0.0")]


# stores -----------------------------------------------------------------------


async def test_a_folder_of_zips_stands_in_for_the_releases(
    trusted_pack_key, tmp_path: Path, clock: Clock, caplog: pytest.LogCaptureFixture
) -> None:
    write_pack(tmp_path, version="1.0.0")
    (tmp_path / "notes.txt").write_text("not a pack")
    # Digits other than 0 to 9 are no version: no header could carry one.
    other_digits = write_pack(tmp_path, version="1.0.\u0661")
    packs = PackCatalog(DirectorySource(tmp_path), ttl_seconds=TTL, clock=clock)

    with caplog.at_level(logging.WARNING):
        first = await packs.packs()
    write_pack(tmp_path, version="1.1.0")
    clock.advance(TTL)
    second = await packs.packs()

    assert served(first) == [("sample-jobs", "1.0.0")]
    assert [version for _, version in served(second)] == ["1.0.0", "1.1.0"]
    assert "notes.txt" in caplog.text
    assert other_digits.name in caplog.text


async def test_a_missing_folder_is_unavailable(
    trusted_pack_key, tmp_path: Path, clock: Clock
) -> None:
    packs = PackCatalog(
        DirectorySource(tmp_path / "none"), ttl_seconds=TTL, clock=clock
    )

    with pytest.raises(PackSourceUnavailableError):
        await packs.packs()


async def test_no_store_is_unavailable(clock: Clock) -> None:
    with pytest.raises(PackSourceUnavailableError):
        await PackCatalog(None, ttl_seconds=TTL, clock=clock).packs()


def test_job_packs_dir_wins_over_github(
    github: FakeGitHub, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The emergency path: a folder on the host while GitHub or the token is down."""
    monkeypatch.setattr(config, "JOB_PACKS_DIR", str(tmp_path))

    assert configured_source() == DirectorySource(tmp_path)


def test_github_is_read_with_both_its_settings(github: FakeGitHub) -> None:
    source = configured_source()

    assert source == GitHubReleases(github.repo, github.token)
    assert github.token not in repr(source)


async def test_a_repository_without_a_token_configures_nothing(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(catalog, "_shared", None)
    monkeypatch.setattr(config, "JOB_PACKS_DIR", "")
    monkeypatch.setattr(
        config, "JOB_PACKS_GITHUB_REPO", "MODSetter/surfsense-job-packs"
    )
    monkeypatch.setattr(config, "JOB_PACKS_GITHUB_TOKEN", "")

    with caplog.at_level(logging.WARNING):
        shared = shared_catalog()

    assert configured_source() is None
    assert "JOB_PACKS_GITHUB_TOKEN" in caplog.text
    with pytest.raises(PackSourceUnavailableError):
        await shared.packs()


def test_one_catalog_is_shared_per_configured_store(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(catalog, "_shared", None)
    monkeypatch.setattr(config, "JOB_PACKS_DIR", str(tmp_path / "a"))
    first = shared_catalog()
    same = shared_catalog()
    monkeypatch.setattr(config, "JOB_PACKS_DIR", str(tmp_path / "b"))

    assert first is same
    assert shared_catalog() is not first
