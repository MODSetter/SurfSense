"""What one install does when the check refuses it or the download fails."""

import logging

import httpx
import pytest

from modules.llm.catalog.local.build import Build, BuildFile, FileRole
from modules.llm.catalog.local.install.plan import InstallPlan, InstallRefusedError
from modules.llm.catalog.local.install_jobs.jobs import FAILED
from modules.llm.catalog.local.install_jobs.steps import install_steps
from modules.llm.providers.llamacpp.download import ChecksumMismatchError

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]

REFUSAL = "This build is too big for this computer. Pick a smaller one."
URL = "https://huggingface.co/r/m/resolve/s/m-Q4_K_M.gguf"
MIRROR = "https://cas-bridge.invalid/m-Q4_K_M.gguf?X-Amz-Signature=secret"

class RefusingService:
    """A catalog whose check refuses, and whose downloader must never run."""

    async def check(self, plan: InstallPlan) -> InstallPlan:
        raise InstallRefusedError(REFUSAL)

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


async def _events(service: object) -> list[dict]:
    return [
        event
        async for event in install_steps(
            service,  
            _plan(),
            select=False,
            model_type=None,
            session_factory=lambda: None,
        )
    ]

async def test_a_refused_plan_ends_the_job_with_its_reason_and_moves_no_bytes() -> None:
    """A refusal is the job's only event: the reason a person reads, then the end."""
    events = await _events(RefusingService())

    assert events == [{"type": "error", "message": REFUSAL}]
    assert events == [{"type": "error", "message": REFUSAL}]

@pytest.mark.parametrize("status", [403, 404])
async def test_a_pinned_file_that_is_gone_ends_the_job_without_the_retry_message(
    status: int, caplog: pytest.LogCaptureFixture
) -> None:
    """A dead pin never comes back at its commit, so a retry is a loop; the log
    names the file, repo and commit so a maintainer can re-pin it."""
    caplog.set_level(logging.WARNING)

    events = await _events(FailingDownloadService(_http_error(status)))

    end = events[-1]
    assert end["type"] == "error"
    assert end != FAILED
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
    assert "retry" in end["message"].lower()
    assert URL in caplog.text


async def test_any_other_http_failure_still_reaches_the_generic_error() -> None:
    """Only a dead pin has its own sentence; a 500 may pass, so it stays FAILED."""
    with pytest.raises(httpx.HTTPStatusError):
        await _events(FailingDownloadService(_http_error(500)))