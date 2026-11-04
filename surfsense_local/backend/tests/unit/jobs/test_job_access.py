"""A paid pack's job runs on a licence that carries its entitlement, as a Business licence and
the Business trial do; a free pack's always; and every paid one under the developer switch."""

from types import SimpleNamespace

import pytest

from modules.jobs.packs.access import DEV_SWITCH, job_access
from modules.jobs.packs.manifest import PackJob, PackManifest

pytestmark = pytest.mark.unit

CODE = "JOB_QUESTIONNAIRE"


def _pack(access: str = "paid", entitlement: str | None = CODE):
    job = PackJob(
        key="security-questionnaire",
        name="Security questionnaire",
        description="Fills one in.",
        runner="workbook-rows/1",
        config="jobs/q/job.json",
        skill=None,
        entitlement=entitlement,
    )
    manifest = PackManifest(
        id="surfsense-security-questionnaire",
        version="1.0.0",
        name="Security questionnaire",
        publisher="SurfSense",
        description="Fills one in.",
        access=access,
        license_file="LICENSE.md",
        jobs=(job,),
        files={"LICENSE.md": "0" * 64},
    )
    return manifest, job


@pytest.fixture
def licence(monkeypatch: pytest.MonkeyPatch):
    """Set what the licence module reports: its state, and the jobs it carries."""

    def held(state: str, jobs=None, plan: str = "business") -> None:
        reported = SimpleNamespace(state=state, plan=plan, jobs=jobs)
        monkeypatch.setattr(
            "modules.jobs.packs.access.status", lambda _session: reported
        )

    monkeypatch.delenv(DEV_SWITCH, raising=False)
    return held


@pytest.mark.parametrize(
    ("plan", "jobs"),
    [
        ("business", "JOB_QUESTIONNAIRE"),
        ("trial", "JOB_OTHER,JOB_QUESTIONNAIRE"),
        ("business", ("JOB_QUESTIONNAIRE",)),
        # As the licence module gives them: the trimmed codes, a list.
        ("business", ["JOB_OTHER", "JOB_QUESTIONNAIRE"]),
        ("business", " JOB_QUESTIONNAIRE , JOB_OTHER "),
    ],
)
def test_a_licence_carrying_the_job_s_entitlement_unlocks_it(licence, plan, jobs):
    """The plan does not decide, the entitlement does: the Business trial is a trial plan with
    the same jobs. Codes come comma-separated in the file, or already split."""
    licence("active", jobs, plan)

    assert job_access(None, *_pack()).allowed


@pytest.mark.parametrize(
    ("state", "jobs", "said"),
    [
        ("none", None, "needs a SurfSense Business licence"),
        ("active", None, "does not include Security questionnaire"),
        ("active", [], "does not include Security questionnaire"),
        ("active", "JOB_OTHER", "does not include Security questionnaire"),
        ("license_expired", CODE, "licence has expired"),
        ("license_expired", None, "does not include Security questionnaire"),
        ("clock_untrusted", CODE, "clock"),
        ("clock_untrusted", "JOB_OTHER", "does not include Security questionnaire"),
    ],
)
def test_without_an_active_licence_carrying_it_the_job_is_refused(
    licence, state, jobs, said
):
    """An expired licence is refused even with the entitlement: its expiry already holds the
    30 days' grace, so the app adds none."""
    licence(state, jobs)

    access = job_access(None, *_pack())

    assert not access.allowed and said in access.reason


def test_a_paid_job_that_names_no_entitlement_never_unlocks(licence):
    """No licence can unlock a paid job whose pack names no code for it."""
    licence("active", CODE)

    access = job_access(None, *_pack(entitlement=None))

    assert not access.allowed and "names no licence entitlement" in access.reason


def test_a_free_pack_and_the_developer_switch_need_no_licence(licence, monkeypatch):
    """A free pack runs without a licence, and the developer switch runs a paid one."""
    licence("none")
    assert job_access(None, *_pack(access="free", entitlement=None)).allowed

    monkeypatch.setenv(DEV_SWITCH, "1")
    assert job_access(None, *_pack()).allowed
