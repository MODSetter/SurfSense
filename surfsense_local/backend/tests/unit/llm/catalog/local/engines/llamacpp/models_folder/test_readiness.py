"""What the install says while a downloaded model becomes one that answers."""

from collections.abc import AsyncIterator

import pytest

from modules.llm.catalog.local.engines.llamacpp.models_folder import readiness
from modules.llm.providers.llamacpp.model_events import LoadProgress

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


def _listed(servable: bool):
    async def wait_until_servable(runtime_url: str, model_id: str) -> bool:
        return servable

    return wait_until_servable


def _stages(*stages: str | None):
    async def warm_model(
        runtime_url: str, model_id: str
    ) -> AsyncIterator[LoadProgress]:
        for stage in stages:
            yield LoadProgress(
                model_id=model_id, status="loading", stage=stage, value=0.5
            )

    return warm_model


async def test_each_load_stage_names_itself(monkeypatch: pytest.MonkeyPatch) -> None:
    """A stage the runtime names gets its own code; one it does not is the model."""
    monkeypatch.setattr(readiness, "wait_until_servable", _listed(True))
    monkeypatch.setattr(
        readiness,
        "warm_model",
        _stages("text_model", "mmproj_model", "spec_model", None),
    )

    steps = [step async for step in readiness.become_ready("http://runtime", "m")]

    assert [(step.kind, step.code) for step in steps] == [
        ("preparing", "preparing_runtime"),
        ("preparing", "loading_model"),
        ("preparing", "loading_image_support"),
        ("preparing", "loading_draft_model"),
        ("preparing", "loading_model"),
        ("complete", "ready"),
    ]
    assert steps[2].message == "Loading image support"


async def test_a_runtime_that_has_not_restarted_says_the_model_comes_later(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The download is done, so the install completes, with its own sentence."""
    monkeypatch.setattr(readiness, "wait_until_servable", _listed(False))

    steps = [step async for step in readiness.become_ready("http://runtime", "m")]

    assert [(step.kind, step.code) for step in steps] == [
        ("preparing", "preparing_runtime"),
        ("complete", "ready_after_restart"),
    ]
