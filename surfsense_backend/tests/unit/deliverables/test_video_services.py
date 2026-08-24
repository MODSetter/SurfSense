from __future__ import annotations

import json
from pathlib import PurePosixPath

import pytest

from app.agents.chat.multi_agent_chat.subagents.builtins.deliverables.tools import (
    prepare_video_project as prepare_service,
    review_video_stills as review_service,
)
from tests.utils.fake_sandbox import FakeSandboxSession

pytestmark = pytest.mark.unit

WORKDIR = PurePosixPath("/workspace/deliverable-job-7")


def _video_scene(number: int) -> prepare_service.VideoScene:
    return prepare_service.VideoScene(
        slide_number=number,
        filename=f"scene-{number}.tsx",
        code=(
            'import React from "react";\n'
            f"const Scene{number} = () => <div>{number}</div>;\n"
            f"export default Scene{number};\n"
        ),
        audio=f"slide-{number}.wav",
    )


async def test_prepare_video_project_writes_typed_json() -> None:
    session = FakeSandboxSession({})
    scene = _video_scene(1)

    result = await prepare_service.prepare_video_project(
        prepare_service.VideoProject(scenes=[scene]),
        session=session,
        workdir=WORKDIR,
    )

    assert result["props_path"] == f"{WORKDIR}/props.json"
    payload = json.loads(session.writes[result["props_path"]])
    assert payload["scenes"][0]["code"] == scene.code
    assert payload["scenes"][0]["filename"] == "scene-1.tsx"
    assert session.commands == []


@pytest.mark.parametrize("scene_count", [12, 13])
async def test_prepare_video_project_enforces_scene_policy(scene_count) -> None:
    if scene_count == 13:
        with pytest.raises(ValueError, match="at most 12 items"):
            prepare_service.VideoProject(
                scenes=[_video_scene(number) for number in range(1, 14)]
            )
        return

    result = await prepare_service.prepare_video_project(
        prepare_service.VideoProject(
            scenes=[_video_scene(number) for number in range(1, scene_count + 1)]
        ),
        session=FakeSandboxSession({}),
        workdir=WORKDIR,
    )
    assert result["scene_count"] == 12


async def test_review_video_stills_rejects_traversal_before_sandbox_access() -> None:
    with pytest.raises(ValueError, match="relative"):
        await review_service.review_video_stills(
            ["../other-job/frame.jpg"],
            session=FakeSandboxSession({}),
            vision_llm=object(),
            workdir=WORKDIR,
        )


async def test_review_video_stills_is_bounded(monkeypatch) -> None:
    still = f"{WORKDIR}/stills/frame.jpg"
    session = FakeSandboxSession({still: b"jpeg"})
    vision_llm = object()
    criterion = review_service.VideoCriterionReview(verdict="pass")
    verdict = review_service.VideoStillReview(
        clipping=criterion,
        overflow=criterion,
        contrast=criterion,
        hierarchy=criterion,
        blank_frames=criterion,
        safe_margins=criterion,
        summary="All sampled frames pass.",
    )

    async def invoke_json(llm, messages, schema):
        assert llm is vision_llm
        assert schema is review_service.VideoStillReview
        assert len(messages[0].content) == 3
        return verdict

    monkeypatch.setattr(review_service, "invoke_json", invoke_json)

    result = await review_service.review_video_stills(
        ["stills/frame.jpg"],
        session=session,
        vision_llm=vision_llm,
        workdir=WORKDIR,
    )

    assert result["status"] == "reviewed"
    assert set(result["review"]) == {
        "clipping",
        "overflow",
        "contrast",
        "hierarchy",
        "blank_frames",
        "safe_margins",
        "summary",
    }


async def test_review_video_stills_fails_safely_without_vision() -> None:
    still = f"{WORKDIR}/frame.jpg"

    result = await review_service.review_video_stills(
        ["frame.jpg"],
        session=FakeSandboxSession({still: b"jpeg"}),
        vision_llm=None,
        workdir=WORKDIR,
    )

    assert result == {
        "status": "unavailable",
        "reason": "No vision-capable model is configured for this workspace",
    }


def test_review_video_stills_normalizes_observed_model_field_names() -> None:
    criterion = {"status": "warning", "evidence": ["frame is close to edge"]}
    review = review_service.VideoStillReview.model_validate(
        {
            "clipping": criterion,
            "overflow": criterion,
            "contrast": criterion,
            "visualHierarchy": criterion,
            "blankFrames": criterion,
            "safeMargins": criterion,
            "summary": {
                "status": "warning",
                "evidence": ["Minor warnings.", "Improve edge spacing."],
            },
        }
    )

    assert review.hierarchy.verdict == "warning"
    assert review.blank_frames.evidence == ["frame is close to edge"]
    assert review.safe_margins.verdict == "warning"
    assert review.summary == "Minor warnings.; Improve edge spacing."


def test_review_video_stills_schema_bounds_evidence() -> None:
    with pytest.raises(ValueError, match="at most 3 items"):
        review_service.VideoCriterionReview(
            verdict="blocking",
            evidence=["one", "two", "three", "four"],
        )
