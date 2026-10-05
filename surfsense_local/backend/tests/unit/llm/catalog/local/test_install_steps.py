"""What one install says at each step, and how it ends when the check refuses it
or the download fails."""

import logging
from contextlib import nullcontext
from datetime import UTC, datetime
from types import SimpleNamespace

import httpx
import pytest

from modules.llm.catalog.local.build import Build, BuildFile, FileRole
from modules.llm.catalog.local.engines.engine import InstallStep
from modules.llm.catalog.local.install.codes import InstallCode
from modules.llm.catalog.local.install.plan import InstallPlan, InstallRefusedError
from modules.llm.catalog.local.install_jobs.jobs import FAILED
from modules.llm.catalog.local.install_jobs.steps import install_steps
from modules.llm.model_type import ModelType
from modules.llm.profile import Tier
from modules.llm.providers.llamacpp.download import ChecksumMismatchError
from modules.llm.providers.types import DownloadProgress

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]

REFUSAL = "This build is too big for this computer. Pick a smaller one."
URL = "https://huggingface.co/r/m/resolve/s/m-Q4_K_M.gguf"
MIRROR = "https://cas-bridge.invalid/m-Q4_K_M.gguf?X-Amz-Signature=secret"


class RefusingService:
    """A catalog whose check refuses, and whose downloader must never run."""

    def __init__(self, refusal: InstallRefusedError) -> None:
        self._refusal = refusal

    async def check(self, plan: InstallPlan) -> InstallPlan:
        raise self._refusal

    def install(self, plan: InstallPlan):
        raise AssertionError("no bytes may move after a refusal")


class FailingDownloadService:
    """A catalog whose check passes and whose download fails with `error`."""

    def __init__(self, error: Exception) -> None:
        self._error = error

    async def check(self, plan: InstallPlan) -> InstallPlan:
        return plan

    def install(self, plan: InstallPlan):
        return self._fail()

    async def _fail(self):
        raise self._error
        yield

    def engine(self, name: str):
        raise AssertionError("a failed download must not reach the engine")


class WarmingEngine:
    """An engine that loads the model before it calls the install done."""

    provider = "llamacpp"
    model_types = (ModelType.TEXT_GEN,)

    async def after_install(self, model_id: str):
        yield InstallStep(
            "preparing", "Loading the model", 0.5, InstallCode.LOADING_MODEL
        )
        yield InstallStep("complete", "Model is ready", code=InstallCode.READY)


class RefusingEngine:
    """An engine that tries the model once it is on disk and turns it down."""

    async def after_install(self, model_id: str):
        yield InstallStep("verifying", "Checking that it finds answers")
        yield InstallStep("error", "It found 6 of 10 answers first.")
        raise AssertionError("nothing runs after the engine's refusal")


class InstallingService:
    """A catalog whose check passes and whose one file downloads."""

    def __init__(self, engine: object | None = None) -> None:
        self._engine = engine or WarmingEngine()

    async def check(self, plan: InstallPlan) -> InstallPlan:
        return plan

    async def install(self, plan: InstallPlan):
        yield DownloadProgress("downloading", 500, 1_000)

    def engine(self, name: str) -> object:
        return self._engine


def _plan() -> InstallPlan:
    build = Build(
        "Q4_K_M",
        (BuildFile(FileRole.WEIGHTS, "m-Q4_K_M.gguf", 1_000, "a" * 64, "r/m", "s"),),
    )
    return InstallPlan("m-Q4_K_M", build, "llamacpp")


def _http_error(status: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", URL)
    response = httpx.Response(status, request=request)
    return httpx.HTTPStatusError(str(status), request=request, response=response)


async def _events(service: object, *, select: bool = False) -> list[dict]:
    return [
        event
        async for event in install_steps(
            service,  # type: ignore[arg-type]
            _plan(),
            select=select,
            model_type=None,
            session_factory=lambda: nullcontext(),  # type: ignore[arg-type,return-value]
        )
    ]


async def test_a_refused_plan_ends_the_job_with_its_reason_and_moves_no_bytes() -> None:
    """A refusal is the job's only event: the reason a person reads, then the end."""
    events = await _events(RefusingService(InstallRefusedError(REFUSAL)))

    assert events == [{"type": "error", "message": REFUSAL, "code": None}]


async def test_a_refusal_with_a_code_carries_it_and_its_raw_numbers() -> None:
    """The sentence stays for an interface that does not know the code; the
    numbers travel raw, so each language formats its own."""
    refusal = InstallRefusedError(
        "This download needs 5.0 GB free; this computer has 2.0 GB.",
        InstallCode.NOT_ENOUGH_DISK,
        needed_bytes=5_000_000_000,
        free_bytes=2_000_000_000,
    )

    events = await _events(RefusingService(refusal))

    assert events == [
        {
            "type": "error",
            "message": "This download needs 5.0 GB free; this computer has 2.0 GB.",
            "code": "not_enough_disk",
            "needed_bytes": 5_000_000_000,
            "free_bytes": 2_000_000_000,
        }
    ]


async def test_every_step_of_an_install_names_what_it_is_doing() -> None:
    """Each frame carries a code beside its English, the engine's own included."""
    events = await _events(InstallingService())

    assert [(event["type"], event["code"]) for event in events] == [
        ("starting", "preparing_download"),
        ("downloading", "downloading"),
        ("verifying", "checking"),
        ("preparing", "loading_model"),
        ("complete", "ready"),
    ]
    assert all(event["message"] for event in events)


async def test_an_install_asked_to_select_says_so_before_it_ends(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Selecting is a step of its own, and the install ends with what it chose."""

    async def choose(session, model_type, provider, name):
        return SimpleNamespace(
            model_type=model_type,
            provider=provider,
            connection_id=None,
            name=name,
            tier=Tier.COMPACT,
            updated_at=datetime(2026, 1, 1, tzinfo=UTC),
        )

    monkeypatch.setattr(
        "modules.llm.catalog.local.install_jobs.steps.choose_model", choose
    )

    events = await _events(InstallingService(), select=True)

    assert [(event["type"], event["code"]) for event in events[-2:]] == [
        ("selecting", "selecting"),
        ("complete", "ready"),
    ]
    assert events[-1]["selection"]["name"] == "m-Q4_K_M"


async def test_an_engine_refusing_the_model_ends_the_job_in_its_words() -> None:
    """A step the engine gave no code to still ends the job, in its own words."""
    events = await _events(InstallingService(RefusingEngine()))

    assert events[-2:] == [
        {
            "type": "verifying",
            "message": "Checking that it finds answers",
            "code": None,
            "progress": None,
        },
        {"type": "error", "message": "It found 6 of 10 answers first.", "code": None},
    ]


@pytest.mark.parametrize("status", [401, 403, 404])
async def test_a_pinned_file_that_is_gone_ends_the_job_without_the_retry_message(
    status: int, caplog: pytest.LogCaptureFixture
) -> None:
    """A deleted, gated or private repo answers 401 and a missing file 404; a
    dead pin never comes back at its commit, so a retry is a loop, and the log
    names the file, repo and commit so a maintainer can re-pin it."""
    caplog.set_level(logging.WARNING)

    events = await _events(FailingDownloadService(_http_error(status)))

    end = events[-1]
    assert end["type"] == "error"
    assert end != FAILED
    assert end["code"] == "file_gone"
    assert "retry" not in end["message"].lower()
    assert URL in caplog.text


async def test_a_redirected_dead_pin_logs_the_pinned_url_not_the_mirror(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Hugging Face redirects a resolve URL to a mirror; when the mirror says
    404, the log still names the repo and commit, and never the signed URL."""
    caplog.set_level(logging.WARNING)
    pinned = httpx.Request("GET", URL)
    redirect = httpx.Response(302, request=pinned, headers={"location": MIRROR})
    mirror = httpx.Request("GET", MIRROR)
    response = httpx.Response(404, request=mirror, history=[redirect])
    error = httpx.HTTPStatusError("404", request=mirror, response=response)

    events = await _events(FailingDownloadService(error))

    assert events[-1]["type"] == "error"
    assert URL in caplog.text
    assert "X-Amz-Signature" not in caplog.text


async def test_a_checksum_mismatch_ends_the_job_saying_a_retry_is_worth_it(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The download worked but the bytes are wrong: retrying is worth a try, and
    the log names the file, repo and commit in case a mirror is rewriting it."""
    caplog.set_level(logging.WARNING)
    mismatch = ChecksumMismatchError(URL, "m-Q4_K_M.gguf", "a" * 64, "b" * 64)

    events = await _events(FailingDownloadService(mismatch))

    end = events[-1]
    assert end["type"] == "error"
    assert end != FAILED
    assert end["code"] == "checksum_mismatch"
    assert "retry" in end["message"].lower()
    assert URL in caplog.text


async def test_any_other_http_failure_still_reaches_the_generic_error() -> None:
    """Only a dead pin has its own sentence; a 500 may pass, so it stays FAILED."""
    with pytest.raises(httpx.HTTPStatusError):
        await _events(FailingDownloadService(_http_error(500)))
