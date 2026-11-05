"""`POST /license/job-pack`: the newest pack a license may run, or a refusal with a code,
answered at the first of contract 6's checks that fails.

Keygen is faked at its transport, the packs are a folder of zips, and the token
bucket is the real one on its per-process fallback.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime, timedelta

import httpx2
import pytest
from fastapi import FastAPI

from license import token_bucket
from license.job_packs import catalog
from license.portal import license_portal
from license.settings import config
from license.tests.github_fake import FakeGitHub
from license.tests.job_pack_portal import PACK_ROUTE, PackPortal
from license.tests.job_pack_samples import QUESTIONNAIRE, pack_zip, write_pack

pytestmark = pytest.mark.unit

FIRM = "lic-firm"
KEY = f"KEY-{FIRM}"
DDQ = ("sample-ddq", "workbook-rows/1", "JOB_DDQ")
UNAVAILABLE = "Jobs cannot be downloaded right now. Try again later."


def ahead(days: int) -> str:
    return (datetime.now(UTC) + timedelta(days=days)).isoformat()


def licensed(portal: PackPortal, license_id: str = FIRM, **fields) -> None:
    """A Business license with the questionnaire, a year from its end, unless `fields` say."""
    record = {
        "plan": "business",
        "jobs": "JOB_QUESTIONNAIRE",
        "expiry": ahead(365),
        **fields,
    }
    portal.keygen.add(license_id, **record)


def refusal(reply: httpx2.Response, status: int) -> tuple[str, str]:
    """Every refusal is `{detail: {code, message}}`, and the message is a sentence."""
    assert reply.status_code == status
    detail = reply.json()["detail"]
    assert set(detail) == {"code", "message"}
    assert detail["message"].endswith(".")
    return detail["code"], detail["message"]


# served -----------------------------------------------------------------------


async def test_an_entitled_license_gets_the_newest_pack_as_its_zip(
    pack_portal: PackPortal, trusted_pack_key
) -> None:
    licensed(pack_portal)
    write_pack(pack_portal.packs, version="1.0.0")
    write_pack(pack_portal.packs, version="1.1.0")

    reply = await pack_portal.ask(KEY)

    assert reply.status_code == 200
    assert reply.content == pack_zip(version="1.1.0")
    assert reply.headers["content-type"] == "application/zip"
    assert (
        reply.headers["content-disposition"]
        == 'attachment; filename="sample-jobs-1.1.0.zip"'
    )
    assert reply.headers["x-job-pack-id"] == "sample-jobs"
    assert reply.headers["x-job-pack-version"] == "1.1.0"
    # It is the firm's paid content: no proxy may keep a copy.
    assert reply.headers["cache-control"] == "no-store"


async def test_a_business_trial_gets_the_pack(
    pack_portal: PackPortal, trusted_pack_key
) -> None:
    licensed(pack_portal, "lic-trial", plan="trial", expiry=ahead(14))
    write_pack(pack_portal.packs)

    reply = await pack_portal.ask("KEY-lic-trial")

    assert reply.status_code == 200


async def test_jobs_written_with_spaces_still_match(
    pack_portal: PackPortal, trusted_pack_key
) -> None:
    licensed(pack_portal, jobs=" JOB_DDQ , JOB_QUESTIONNAIRE ")
    write_pack(pack_portal.packs, jobs=(QUESTIONNAIRE, DDQ))

    reply = await pack_portal.ask(KEY)

    assert reply.status_code == 200


@pytest.mark.parametrize("installed", ["1.1.0", "1.1.1", "10.0.0"])
async def test_an_installed_version_as_new_or_newer_is_answered_204(
    pack_portal: PackPortal, trusted_pack_key, installed: str
) -> None:
    licensed(pack_portal)
    write_pack(pack_portal.packs, version="1.0.0")
    write_pack(pack_portal.packs, version="1.1.0")

    reply = await pack_portal.ask(KEY, installed_version=installed)

    assert reply.status_code == 204
    assert reply.content == b""
    assert reply.headers["x-job-pack-id"] == "sample-jobs"
    assert reply.headers["x-job-pack-version"] == "1.1.0"
    assert reply.headers["cache-control"] == "no-store"
    assert "content-disposition" not in reply.headers


async def test_an_older_installed_version_gets_the_newer_pack(
    pack_portal: PackPortal, trusted_pack_key
) -> None:
    licensed(pack_portal)
    write_pack(pack_portal.packs, version="1.10.0")

    reply = await pack_portal.ask(KEY, installed_version="1.9.0")

    assert reply.status_code == 200
    assert reply.headers["x-job-pack-version"] == "1.10.0"


async def test_a_version_the_app_could_not_send_back_is_never_served(
    pack_portal: PackPortal, trusted_pack_key
) -> None:
    """The app names its installed version in every later request, each part at most 9
    digits, so a pack it could not name would leave it with no answer for good."""
    licensed(pack_portal)
    write_pack(pack_portal.packs, version="1.0.0")
    write_pack(pack_portal.packs, version="1.0.2026110301")

    reply = await pack_portal.ask(KEY)
    again = await pack_portal.ask(
        KEY, installed_version=reply.headers["x-job-pack-version"]
    )

    assert reply.status_code == 200
    assert reply.headers["x-job-pack-version"] == "1.0.0"
    assert again.status_code == 204


async def test_a_version_written_in_other_digits_than_ascii_is_never_served(
    pack_portal: PackPortal, trusted_pack_key
) -> None:
    """Python's \\d takes any script's digits, which no header can carry."""
    licensed(pack_portal)
    write_pack(pack_portal.packs, version="1.0.0")
    write_pack(pack_portal.packs, version="1.0.\u0661")

    reply = await pack_portal.ask(KEY)

    assert reply.status_code == 200
    assert reply.headers["x-job-pack-version"] == "1.0.0"


async def test_a_pack_naming_a_runner_the_app_lacks_is_passed_over(
    pack_portal: PackPortal, trusted_pack_key
) -> None:
    licensed(pack_portal)
    write_pack(pack_portal.packs, version="1.0.0")
    write_pack(
        pack_portal.packs,
        version="1.1.0",
        jobs=(("sample-questionnaire", "workbook-rows/2", "JOB_QUESTIONNAIRE"),),
    )

    reply = await pack_portal.ask(KEY)

    assert reply.status_code == 200
    assert reply.headers["x-job-pack-version"] == "1.0.0"


async def test_an_app_without_the_packs_runner_needs_a_newer_version(
    pack_portal: PackPortal, trusted_pack_key
) -> None:
    licensed(pack_portal)
    write_pack(
        pack_portal.packs,
        jobs=(("sample-questionnaire", "workbook-rows/2", "JOB_QUESTIONNAIRE"),),
    )

    reply = await pack_portal.ask(KEY)

    assert refusal(reply, 409) == (
        "needs_newer_app",
        "This job needs a newer version of SurfSense. Update the app, then try again.",
    )


# refused, in contract order ---------------------------------------------------


@pytest.mark.parametrize(
    "body",
    [
        pytest.param({"key": KEY, "entitlement": "JOB_QUESTIONNAIRE"}, id="no runners"),
        pytest.param(
            {"key": KEY, "entitlement": "job", "runners": ["workbook-rows/1"]},
            id="an entitlement in lower case",
        ),
        pytest.param(
            {
                "key": KEY,
                "entitlement": "JOB_QUESTIONNAIRE",
                "runners": ["workbook-rows/1"],
                "installed_version": "1.0",
            },
            id="a two-part version",
        ),
        pytest.param(
            {
                "key": KEY,
                "entitlement": "JOB_QUESTIONNAIRE",
                "runners": ["workbook-rows/1"],
                "installed_version": "1.0.\u0661",
            },
            id="a version digit that is not ASCII",
        ),
        pytest.param(
            {"key": KEY, "entitlement": "JOB_QUESTIONNAIRE", "runners": []},
            id="no runner",
        ),
        pytest.param(
            {
                "key": KEY,
                "entitlement": "JOB_QUESTIONNAIRE",
                "runners": [f"runner-{n}/1" for n in range(17)],
            },
            id="seventeen runners",
        ),
        pytest.param(
            {"key": KEY, "entitlement": "JOB_QUESTIONNAIRE", "runners": ["Rows/1"]},
            id="a runner in capitals",
        ),
        pytest.param(
            {
                "key": KEY + "K" * 1024,
                "entitlement": "JOB_QUESTIONNAIRE",
                "runners": ["workbook-rows/1"],
            },
            id="a key too long",
        ),
    ],
)
async def test_a_malformed_request_is_422_and_echoes_nothing(
    pack_portal: PackPortal, body: dict
) -> None:
    """The body carries a license key, so the refusal describes it and never repeats it."""
    reply = await pack_portal.post(PACK_ROUTE, body)

    assert reply.status_code == 422
    errors = reply.json()["detail"]
    assert errors
    assert all(set(error) == {"type", "loc", "msg"} for error in errors)
    assert KEY not in reply.text
    assert pack_portal.keygen.requests == []


async def test_a_body_that_is_not_json_is_422_and_echoes_nothing(
    pack_portal: PackPortal,
) -> None:
    reply = await pack_portal.post(PACK_ROUTE, content=f'{{"key": "{KEY}"'.encode())

    assert reply.status_code == 422
    assert all(set(e) == {"type", "loc", "msg"} for e in reply.json()["detail"])
    assert KEY not in reply.text


async def test_a_job_surfsense_does_not_sell_is_422_before_any_keygen_call(
    pack_portal: PackPortal,
) -> None:
    reply = await pack_portal.ask(KEY, "JOB_NOT_SOLD")

    assert refusal(reply, 422) == (
        "unknown_job",
        "SurfSense has no job with that code.",
    )
    assert pack_portal.keygen.requests == []


async def test_an_unknown_key_is_404(pack_portal: PackPortal) -> None:
    reply = await pack_portal.ask("KEY-nobody")

    assert refusal(reply, 404) == ("license_not_found", "No license has that key.")


async def test_an_expired_license_is_refused_while_the_refresh_still_serves_its_file(
    pack_portal: PackPortal, trusted_pack_key
) -> None:
    """A Business license's expiry already holds the 30 days after the year paid for."""
    licensed(pack_portal, expiry=ahead(-1))
    write_pack(pack_portal.packs)

    pack = await pack_portal.ask(KEY)
    refreshed = await pack_portal.refresh(KEY)

    code, message = refusal(pack, 403)
    assert code == "license_not_valid"
    assert message == "This license cannot download jobs (EXPIRED)."
    assert refreshed.status_code == 200


async def test_a_suspended_license_gets_no_pack(
    pack_portal: PackPortal, trusted_pack_key
) -> None:
    licensed(pack_portal, status="SUSPENDED")
    write_pack(pack_portal.packs)

    reply = await pack_portal.ask(KEY)

    assert refusal(reply, 403) == (
        "license_not_valid",
        "This license cannot download jobs (SUSPENDED).",
    )


@pytest.mark.parametrize(
    "fields",
    [
        pytest.param({"plan": "individual", "jobs": ""}, id="an Individual license"),
        pytest.param({"jobs": "JOB_DDQ"}, id="a license with another job"),
    ],
)
async def test_a_license_without_the_job_is_refused(
    pack_portal: PackPortal, trusted_pack_key, fields: dict
) -> None:
    licensed(pack_portal, **fields)
    write_pack(pack_portal.packs)

    reply = await pack_portal.ask(KEY)

    assert refusal(reply, 403) == (
        "job_not_included",
        "This license does not include that job. Jobs come with a Business license, "
        "or its 14-day trial.",
    )


async def test_the_license_is_checked_before_the_store_is_read(
    pack_portal: PackPortal, github: FakeGitHub, trusted_pack_key
) -> None:
    licensed(pack_portal, jobs="JOB_DDQ")
    github.publish("sample-jobs-v1.0.0", "sample-jobs-1.0.0.zip", pack_zip())

    unknown = await pack_portal.ask("KEY-nobody")
    without = await pack_portal.ask(KEY)

    assert (unknown.status_code, without.status_code) == (404, 403)
    # The license's jobs come before its jobs against the packs': never pack_not_covered.
    assert refusal(without, 403)[0] == "job_not_included"
    assert github.requests == []


async def test_a_pack_holding_a_job_the_license_lacks_is_withheld(
    pack_portal: PackPortal, trusted_pack_key
) -> None:
    """The app installs every job of the pack, so the license would get one it did not buy.

    A code of its own: the license does include the job asked for, so the app must not
    say it does not.
    """
    licensed(pack_portal)
    write_pack(pack_portal.packs, jobs=(QUESTIONNAIRE, DDQ))

    reply = await pack_portal.ask(KEY)

    assert refusal(reply, 403) == (
        "pack_not_covered",
        "Every pack of that job also holds a job this license does not include.",
    )


async def test_no_pack_published_for_the_job_is_503(
    pack_portal: PackPortal, caplog: pytest.LogCaptureFixture
) -> None:
    licensed(pack_portal)

    with caplog.at_level(logging.ERROR):
        reply = await pack_portal.ask(KEY)

    assert refusal(reply, 503) == ("job_packs_unavailable", UNAVAILABLE)
    assert "JOB_QUESTIONNAIRE" in caplog.text


async def test_no_store_is_503(
    pack_portal: PackPortal, monkeypatch: pytest.MonkeyPatch
) -> None:
    licensed(pack_portal)
    monkeypatch.setattr(config, "JOB_PACKS_DIR", "")

    reply = await pack_portal.ask(KEY)

    assert refusal(reply, 503) == ("job_packs_unavailable", UNAVAILABLE)


async def test_any_store_exception_is_503(
    pack_portal: PackPortal, monkeypatch: pytest.MonkeyPatch
) -> None:
    licensed(pack_portal)

    async def broken(self) -> tuple:
        raise ValueError("a bug in the catalog")

    monkeypatch.setattr(catalog.PackCatalog, "packs", broken)

    reply = await pack_portal.ask(KEY)

    assert refusal(reply, 503) == ("job_packs_unavailable", UNAVAILABLE)


async def test_keygen_down_is_503(pack_portal: PackPortal) -> None:
    pack_portal.keygen.down = True

    reply = await pack_portal.ask(KEY)

    assert refusal(reply, 503) == (
        "job_packs_unavailable",
        "Could not check that license right now. Try again later.",
    )


async def test_a_validation_without_a_code_is_503_never_license_not_found(
    pack_portal: PackPortal,
) -> None:
    """The license exists; license_not_found would tell the app it has none."""
    licensed(pack_portal)
    pack_portal.keygen.codeless = True

    reply = await pack_portal.ask(KEY)

    assert refusal(reply, 503) == (
        "job_packs_unavailable",
        "Could not check that license right now. Try again later.",
    )


# the key and the limits -------------------------------------------------------


async def test_the_key_is_never_in_a_bucket_name_or_a_log(
    pack_portal: PackPortal, trusted_pack_key, caplog: pytest.LogCaptureFixture
) -> None:
    licensed(pack_portal)
    write_pack(pack_portal.packs)

    with caplog.at_level(logging.DEBUG):
        served = await pack_portal.ask(KEY)
        await pack_portal.post(PACK_ROUTE, {"key": KEY})
        await pack_portal.ask(KEY, "JOB_NOT_SOLD")
        pack_portal.keygen.down = True
        await pack_portal.ask(KEY)

    assert served.status_code == 200
    assert KEY not in caplog.text
    buckets = list(token_bucket._memory_buckets)
    assert not any(KEY in name for name in buckets)
    digest = hashlib.sha256(KEY.encode()).hexdigest()[:32]
    assert f"license:job-pack:key:{digest}" in buckets


async def test_the_key_bucket_bites_across_callers(
    pack_portal: PackPortal, trusted_pack_key, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A firm shares one key; a leaked one is still bounded."""
    licensed(pack_portal)
    write_pack(pack_portal.packs)
    monkeypatch.setattr(config, "LICENSE_JOB_PACK_RATE_LIMIT_PER_HOUR", 2)

    replies = [await pack_portal.ask(KEY, ip=f"203.0.113.{n}") for n in range(3)]

    assert [reply.status_code for reply in replies[:2]] == [200, 200]
    assert refusal(replies[2], 429) == (
        "rate_limited",
        "Too many requests. Try again later.",
    )


async def test_the_address_bucket_bites_across_keys(
    pack_portal: PackPortal, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One caller trying keys is still one caller."""
    monkeypatch.setattr(config, "LICENSE_JOB_PACK_RATE_LIMIT_IP_PER_HOUR", 2)

    codes = [(await pack_portal.ask(f"KEY-guess-{n}")).status_code for n in range(3)]

    assert codes == [404, 404, 429]


async def test_spending_the_refresh_buckets_leaves_the_pack_routes(
    pack_portal: PackPortal, trusted_pack_key, monkeypatch: pytest.MonkeyPatch
) -> None:
    licensed(pack_portal)
    write_pack(pack_portal.packs)
    monkeypatch.setattr(config, "LICENSE_REFRESH_RATE_LIMIT_PER_HOUR", 1)
    monkeypatch.setattr(config, "LICENSE_REFRESH_RATE_LIMIT_IP_PER_HOUR", 1)

    refreshes = [(await pack_portal.refresh(KEY)).status_code for _ in range(2)]
    pack = await pack_portal.ask(KEY)

    assert refreshes == [200, 429]
    assert pack.status_code == 200


async def test_the_portal_serves_the_route(pack_portal: PackPortal) -> None:
    portal = license_portal()
    assert portal is not None
    app = FastAPI()
    app.include_router(portal)

    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app), base_url="http://portal"
    ) as client:
        reply = await client.post(
            PACK_ROUTE,
            json={"key": KEY, "entitlement": "JOB_NOT_SOLD", "runners": ["rows/1"]},
        )

    assert refusal(reply, 422)[0] == "unknown_job"
