"""What a signed pack must also be to take the installed one's place: a download carries the job
asked for, holds no job the licence lacks and is newer; an import is the same version or newer;
neither while a run of the pack is under way."""

import pytest

from modules.jobs.packs.delivery.acceptance import accept_delivered, accept_imported
from modules.jobs.packs.install import Accept
from modules.jobs.packs.manifest import PackJob, PackManifest, PackRefusedError

pytestmark = pytest.mark.unit

ASKED = "JOB_QUESTIONNAIRE"
HELD = frozenset({ASKED, "JOB_OTHER"})


def manifest(
    version: str = "1.0.0",
    entitlements: tuple[str | None, ...] = (ASKED,),
    pack_id: str = "surfsense-jobs",
) -> PackManifest:
    """A paid pack with one job per entitlement."""
    return PackManifest(
        id=pack_id,
        version=version,
        name="SurfSense jobs",
        publisher="SurfSense",
        description="Jobs.",
        access="paid",
        license_file="LICENSE.md",
        jobs=tuple(
            PackJob(
                key=f"job-{n}",
                name=f"Job {n}",
                description="A job.",
                runner="workbook-rows/1",
                config="job.json",
                skill=None,
                entitlement=entitlement,
            )
            for n, entitlement in enumerate(entitlements)
        ),
        files={"LICENSE.md": "0" * 64, "job.json": "0" * 64},
    )


def never(_pack_id: str) -> bool:
    """No run of any pack is under way."""
    return False


def refusal(
    accept: Accept, new: PackManifest, installed: list[PackManifest]
) -> str | None:
    """The code `accept` refuses `new` with over `installed`; None when it accepts."""
    try:
        accept(new, installed)
    except PackRefusedError as refused:
        return refused.code
    return None


def test_a_download_is_accepted_when_newer_or_when_none_is_installed() -> None:
    """Versions compare as numbers: 1.10.0 is newer than 1.9.0."""
    accept = accept_delivered(ASKED, HELD, never)

    assert refusal(accept, manifest("1.0.0"), []) is None
    assert refusal(accept, manifest("1.10.0"), [manifest("1.9.0")]) is None


def test_a_download_without_the_job_asked_for_is_the_wrong_job() -> None:
    """The server answered for another code: nothing of it installs."""
    accept = accept_delivered(ASKED, HELD, never)

    assert (
        refusal(accept, manifest(entitlements=("JOB_OTHER",)), []) == "PACK_WRONG_JOB"
    )


@pytest.mark.parametrize(
    "entitlements", [(ASKED, "JOB_UNSOLD"), (ASKED, None)], ids=["lacking", "missing"]
)
def test_a_download_holding_a_job_the_licence_lacks_is_not_included(
    entitlements: tuple[str | None, ...],
) -> None:
    """Every job of the pack must be one the licence lists, so the whole pack runs."""
    accept = accept_delivered(ASKED, HELD, never)

    assert (
        refusal(accept, manifest(entitlements=entitlements), []) == "PACK_NOT_INCLUDED"
    )


@pytest.mark.parametrize(
    "installed",
    [
        manifest("1.0.0"),
        manifest("1.2.0"),
        manifest("2.0.0", pack_id="hand-imported-jobs"),
    ],
    ids=["same", "older", "another id"],
)
def test_a_download_not_newer_than_the_installed_job_is_not_newer(
    installed: PackManifest,
) -> None:
    """A server that sends a pack anyway never takes a version back, under any id."""
    accept = accept_delivered(ASKED, HELD, never)

    assert refusal(accept, manifest("1.0.0"), [installed]) == "PACK_NOT_NEWER"


def test_a_pack_without_the_job_does_not_count_as_installed() -> None:
    """Another pack, for another job, is no version of this one."""
    accept = accept_delivered(ASKED, HELD, never)
    other = manifest("9.0.0", entitlements=("JOB_OTHER",), pack_id="other-jobs")

    assert refusal(accept, manifest("1.0.0"), [other]) is None


def test_a_download_waits_while_a_run_of_the_pack_is_under_way() -> None:
    """The runner reads the pack's files by path while it runs."""
    accept = accept_delivered(ASKED, HELD, lambda pack_id: pack_id == "surfsense-jobs")

    assert refusal(accept, manifest("1.1.0"), [manifest("1.0.0")]) == "PACK_IN_USE"


def test_an_import_may_be_the_same_version_or_newer_but_not_older() -> None:
    """The same signed pack imports again; an older one says which is installed."""
    accept = accept_imported(never)

    assert refusal(accept, manifest("1.0.0"), [manifest("1.0.0")]) is None
    assert refusal(accept, manifest("1.1.0"), [manifest("1.0.0")]) is None
    with pytest.raises(PackRefusedError) as older:
        accept(manifest("1.0.0"), [manifest("1.0.10")])
    assert older.value.code == "PACK_OLDER"
    assert older.value.message == (
        "This is SurfSense jobs 1.0.0, older than the installed 1.0.10."
    )


def test_an_import_waits_while_a_run_of_the_pack_is_under_way() -> None:
    """As a download does: the files a run reads stay until it ends."""
    accept = accept_imported(lambda _pack_id: True)

    assert refusal(accept, manifest("1.1.0"), [manifest("1.0.0")]) == "PACK_IN_USE"
