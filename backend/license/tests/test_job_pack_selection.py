"""Which pack a license and an app get: covered by the license, runnable by the app, newest."""

from __future__ import annotations

import pytest

from license.job_packs.manifest import PackJob
from license.job_packs.selection import Choice, choose, is_current
from license.job_packs.verify import PublishedPack

pytestmark = pytest.mark.unit

QUESTIONS = "JOB_QUESTIONNAIRE"
APP = ("workbook-rows/1",)
HELD = (QUESTIONS,)


def pack(
    version: str, *jobs: tuple[str, str], pack_id: str = "security-questionnaire"
) -> PublishedPack:
    """A checked pack whose jobs are (entitlement, runner) pairs."""
    pairs = jobs or ((QUESTIONS, "workbook-rows/1"),)
    return PublishedPack(
        id=pack_id,
        version=version,
        jobs=tuple(
            PackJob(key=f"job-{n}", runner=runner, entitlement=entitlement)
            for n, (entitlement, runner) in enumerate(pairs)
        ),
        data=f"{pack_id}-{version}".encode(),
    )


def test_versions_compare_as_numbers() -> None:
    newest = pack("1.10.0")
    packs = [pack("1.9.0"), newest, pack("1.2.30")]

    assert choose(packs, QUESTIONS, APP, HELD) == Choice(newest)


def test_a_pack_with_one_runner_the_app_lacks_is_passed_over() -> None:
    """The app refuses a whole pack that names a runner it does not have."""
    runnable = pack("1.0.0")
    newer = pack(
        "1.1.0", (QUESTIONS, "workbook-rows/1"), (QUESTIONS, "workbook-rows/2")
    )

    assert choose([runnable, newer], QUESTIONS, APP, HELD) == Choice(runnable)


def test_only_packs_with_a_job_for_the_entitlement_count() -> None:
    questionnaire = pack("1.0.0")
    other = pack("9.0.0", ("JOB_OTHER", "workbook-rows/1"), pack_id="other-jobs")
    packs = [questionnaire, other]

    assert choose(packs, QUESTIONS, APP, (QUESTIONS, "JOB_OTHER")) == Choice(
        questionnaire
    )
    assert choose(packs, "JOB_UNPUBLISHED", APP, HELD) == Choice(None, "unpublished")
    assert choose([], QUESTIONS, APP, HELD) == Choice(None, "unpublished")


def test_a_pack_holding_a_job_the_license_lacks_is_withheld() -> None:
    """An app installs every job of a pack it accepts, so a license gets only packs it covers."""
    covered = pack("1.0.0")
    wider = pack(
        "2.0.0", (QUESTIONS, "workbook-rows/1"), ("JOB_DDQ", "workbook-rows/1")
    )

    assert choose([covered, wider], QUESTIONS, APP, HELD) == Choice(covered)
    assert choose([wider], QUESTIONS, APP, HELD) == Choice(None, "not_covered")
    assert choose([wider], QUESTIONS, APP, ("JOB_DDQ", QUESTIONS)) == Choice(wider)


def test_a_newer_app_is_needed_only_when_a_covered_pack_has_the_job() -> None:
    needs_runner = pack("1.0.0", (QUESTIONS, "workbook-rows/2"))
    not_covered = pack(
        "1.0.0", (QUESTIONS, "workbook-rows/2"), ("JOB_DDQ", "workbook-rows/2")
    )

    assert choose([needs_runner], QUESTIONS, APP, HELD) == Choice(
        None, "needs_newer_app"
    )
    assert choose([not_covered], QUESTIONS, APP, HELD) == Choice(None, "not_covered")


def test_the_installed_version_is_current_when_the_same_or_newer() -> None:
    served = pack("1.0.9")

    assert is_current("1.0.9", served)
    assert is_current("1.0.10", served)
    assert not is_current("1.0.8", served)
    assert not is_current(None, served)
