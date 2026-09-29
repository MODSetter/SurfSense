"""What one install does when the check refuses it."""

import pytest

from modules.llm.catalog.local.build import Build, BuildFile, FileRole
from modules.llm.catalog.local.install.plan import InstallPlan, InstallRefusedError
from modules.llm.catalog.local.install_jobs.steps import install_steps

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]

REFUSAL = "This build is too big for this computer. Pick a smaller one."


class RefusingService:
    """A catalog whose check refuses, and whose downloader must never run."""

    async def check(self, plan: InstallPlan) -> InstallPlan:
        raise InstallRefusedError(REFUSAL)

    def install(self, plan: InstallPlan):
        raise AssertionError("no bytes may move after a refusal")


async def test_a_refused_plan_ends_the_job_with_its_reason_and_moves_no_bytes() -> None:
    """A refusal is the job's only event: the reason a person reads, then the end."""
    build = Build(
        "Q4_K_M",
        (BuildFile(FileRole.WEIGHTS, "m-Q4_K_M.gguf", 1_000, "a" * 64, "r/m", "s"),),
    )
    plan = InstallPlan("m-Q4_K_M", build, "llamacpp")

    events = [
        event
        async for event in install_steps(
            RefusingService(),  # type: ignore[arg-type]
            plan,
            select=False,
            model_type=None,
            session_factory=lambda: None,  # type: ignore[arg-type,return-value]
        )
    ]

    assert events == [{"type": "error", "message": REFUSAL}]
