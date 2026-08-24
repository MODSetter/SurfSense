from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from app.artifacts.service import ArtifactSaved
from app.deliverables.video import executor
from tests.utils.fake_sandbox import FakeSandboxSession


def _scene(number: int = 1) -> executor.AuthoredVideoScene:
    return executor.AuthoredVideoScene(
        slide_number=number,
        filename=f"scene-{number}.tsx",
        on_screen_markdown=f"Scene {number}",
        transcript=f"Narration {number}",
        code=(
            'import React from "react";\n'
            f"const Scene{number}=()=> <div>{number}</div>;\n"
            f"export default Scene{number};"
        ),
    )


def _authored(count: int = 1) -> executor.AuthoredVideo:
    return executor.AuthoredVideo(scenes=[_scene(i) for i in range(1, count + 1)])


def _job(**overrides):
    values = {
        "id": 7,
        "kind": "video",
        "title": "Quarterly update",
        "workspace_id": 3,
        "thread_id": 11,
        "tool_call_id": "tool-1",
        "celery_task_id": "deliverable-job:7:attempt:1",
        "attempt_count": 1,
        "request": {
            "version": 1,
            "brief": "Explain the quarter",
            "source_references": ["/documents/report.pdf"],
            "revision_artifact_id": None,
            "root_thread_id": 11,
        },
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_video_request_is_strict_and_bound_to_a_root_thread() -> None:
    request = executor.VideoJobRequestV1.model_validate(_job().request)
    assert request.root_thread_id == 11

    with pytest.raises(ValidationError):
        executor.VideoJobRequestV1.model_validate({**_job().request, "version": 2})
    with pytest.raises(ValidationError):
        executor.VideoJobRequestV1.model_validate(
            {**_job().request, "revision_artifact_id": True}
        )
    with pytest.raises(ValidationError):
        executor.VideoJobRequestV1.model_validate(
            {
                **_job().request,
                "source_references": ["source"] * 26,
            }
        )


def test_authored_video_enforces_twelve_scene_limit() -> None:
    assert len(_authored(12).scenes) == 12
    with pytest.raises(ValidationError, match="at most 12"):
        _authored(13)


def test_creative_draft_is_normalized_to_backend_owned_scene_identity() -> None:
    draft = executor._CreativeVideoDraft.model_validate(
        {
            "title": "Ignored model title",
            "durationSec": 30,
            "language": "en",
            "scenes": [
                {
                    "id": "opening",
                    "durationSec": 10,
                    "narration": "Opening narration",
                    "onScreenMarkdown": "# Opening",
                    "tsx": "export default () => <div>Opening</div>;",
                },
                {
                    "id": "ending",
                    "narration": "Ending narration",
                    "onScreenMarkdown": "# Ending",
                    "tsx_module": "export default () => <div>Ending</div>;",
                },
            ],
        }
    )

    authored = executor._normalize_creative_video(draft)

    assert authored.language == "en"
    assert [(scene.slide_number, scene.filename) for scene in authored.scenes] == [
        (1, "scene-01.tsx"),
        (2, "scene-02.tsx"),
    ]
    assert authored.scenes[0].transcript == "Opening narration"
    assert authored.scenes[0].on_screen_markdown == "# Opening"
    assert authored.scenes[0].code == "export default () => <div>Opening</div>;"


def test_video_repair_preserves_identity_narration_and_language() -> None:
    authored = executor.AuthoredVideo(language="en", scenes=[_scene(1), _scene(2)])
    repair = executor._VideoRepairDraft.model_validate(
        {
            "language": "fr",
            "scenes": [
                {
                    "slide_number": 9,
                    "filename": "changed.tsx",
                    "narration": "Changed narration",
                    "onScreenMarkdown": "Repaired one",
                    "tsx": "export default () => <div>Repaired one</div>;",
                },
                {
                    "on_screen_markdown": "Repaired two",
                    "code": "export default () => <div>Repaired two</div>;",
                },
            ],
        }
    )

    repaired = executor._merge_video_repair(authored, repair)

    assert repaired.language == "en"
    assert [
        (scene.slide_number, scene.filename, scene.transcript)
        for scene in repaired.scenes
    ] == [
        (scene.slide_number, scene.filename, scene.transcript)
        for scene in authored.scenes
    ]
    assert [scene.on_screen_markdown for scene in repaired.scenes] == [
        "Repaired one",
        "Repaired two",
    ]
    assert repaired.scenes[0].code == ("export default () => <div>Repaired one</div>;")


def test_video_repair_rejects_changed_scene_count() -> None:
    repair = executor._VideoRepairDraft.model_validate(
        {
            "scenes": [
                {
                    "on_screen_markdown": "Only one",
                    "code": "export default () => <div>Only one</div>;",
                }
            ]
        }
    )

    with pytest.raises(ValueError, match="changed scene count"):
        executor._merge_video_repair(_authored(2), repair)


async def test_executor_runs_explicit_stages_and_owns_sandbox(monkeypatch) -> None:
    stages: list[str] = []
    heartbeats: list[tuple[str, int]] = []
    sandbox = FakeSandboxSession()
    session = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())

    class Registry:
        async def get_session(self, owner_id, workspace_id):
            assert (owner_id, workspace_id) == ("deliverable-job-7-attempt-1", 3)
            return sandbox

    async def get_registry():
        return Registry()

    async def author(*_args):
        stages.append("author")
        return _authored()

    async def narration(*_args, **_kwargs):
        stages.append("narration")
        return [{"slide_number": 1, "audio": "slide-1.wav", "duration_seconds": 5}]

    async def prepare(*_args, **_kwargs):
        stages.append("prepare")
        return {"props_path": "/workspace/deliverable-job-7/props.json"}

    async def preflight(*_args, **_kwargs):
        stages.extend(("preflight", "stills", "review"))
        return None

    async def render(*_args, **_kwargs):
        stages.append("render")

    async def verify(*_args, **_kwargs):
        stages.append("verify")
        return SimpleNamespace(verified=True, findings=())

    async def save(*_args, **_kwargs):
        stages.append("save")
        return ArtifactSaved(
            status="saved",
            artifact_id=19,
            generation=1,
            title="Quarterly update",
            files=[],
        )

    async def vision(*_args, **_kwargs):
        return None

    async def heartbeat(_session, job_id, *, phase, progress, task_id):
        assert job_id == 7
        assert task_id == "deliverable-job:7:attempt:1"
        heartbeats.append((phase, progress))
        return SimpleNamespace(id=job_id)

    monkeypatch.setattr(executor, "get_registry", get_registry)
    monkeypatch.setattr(executor, "heartbeat_deliverable_job", heartbeat)
    monkeypatch.setattr(executor, "_author_video", author)
    monkeypatch.setattr(executor, "synthesize_narration", narration)
    monkeypatch.setattr(executor, "prepare_video_project", prepare)
    monkeypatch.setattr(executor, "_preflight_and_review", preflight)
    monkeypatch.setattr(executor, "_render", render)
    monkeypatch.setattr(executor, "verify_artifact", verify)
    monkeypatch.setattr(executor, "_save_verified", save)
    monkeypatch.setattr(executor, "get_vision_llm", vision)

    result = await executor.execute_video_deliverable(session, _job(), object())

    assert stages == [
        "author",
        "narration",
        "prepare",
        "preflight",
        "stills",
        "review",
        "render",
        "verify",
        "save",
    ]
    assert heartbeats == [
        ("preparing", 5),
        ("authoring", 10),
        ("narrating", 25),
        ("preparing", 40),
        ("reviewing", 50),
        ("rendering", 65),
        ("verifying", 85),
        ("saving", 95),
    ]
    assert all(0 <= progress < 100 for _, progress in heartbeats)
    assert session.commit.await_count == len(heartbeats)
    assert result.artifact_id == 19
    assert result.duration_seconds == 5


async def test_executor_rejects_duration_above_180_seconds(monkeypatch) -> None:
    sandbox = FakeSandboxSession()

    class Registry:
        async def get_session(self, *_args):
            return sandbox

    async def get_registry():
        return Registry()

    async def author(*_args):
        return _authored()

    async def narration(*_args, **_kwargs):
        return [{"slide_number": 1, "audio": "slide-1.wav", "duration_seconds": 180.1}]

    async def heartbeat(*_args, **_kwargs):
        return None

    monkeypatch.setattr(executor, "get_registry", get_registry)
    monkeypatch.setattr(executor, "_heartbeat", heartbeat)
    monkeypatch.setattr(executor, "_author_video", author)
    monkeypatch.setattr(executor, "synthesize_narration", narration)

    with pytest.raises(ValueError, match="180-second"):
        await executor.execute_video_deliverable(object(), _job(), object())


async def test_executor_stops_after_two_repairs(monkeypatch) -> None:
    sandbox = FakeSandboxSession()
    repairs = 0
    progress_updates = []
    preflights = iter(("compile failed", None, None))

    class Registry:
        async def get_session(self, *_args):
            return sandbox

    async def get_registry():
        return Registry()

    async def author(*_args):
        return _authored()

    async def narration(*_args, **_kwargs):
        return [{"slide_number": 1, "audio": "slide-1.wav", "duration_seconds": 5}]

    async def prepare(*_args, **_kwargs):
        return {"props_path": "/workspace/deliverable-job-7/props.json"}

    async def preflight(*_args, **_kwargs):
        return next(preflights)

    async def repair(_llm, authored, _finding):
        nonlocal repairs
        repairs += 1
        return authored

    async def noop(*_args, **_kwargs):
        return None

    async def failed_verify(*_args, **_kwargs):
        return SimpleNamespace(verified=False, findings=("bad frame",))

    async def heartbeat(_session, _job_id, _phase, progress, **_kwargs):
        progress_updates.append(progress)

    monkeypatch.setattr(executor, "get_registry", get_registry)
    monkeypatch.setattr(executor, "_heartbeat", heartbeat)
    monkeypatch.setattr(executor, "_author_video", author)
    monkeypatch.setattr(executor, "synthesize_narration", narration)
    monkeypatch.setattr(executor, "prepare_video_project", prepare)
    monkeypatch.setattr(executor, "_preflight_and_review", preflight)
    monkeypatch.setattr(executor, "_repair_video", repair)
    monkeypatch.setattr(executor, "_render", noop)
    monkeypatch.setattr(executor, "verify_artifact", failed_verify)
    monkeypatch.setattr(executor, "get_vision_llm", noop)

    with pytest.raises(RuntimeError, match="verification failed"):
        await executor.execute_video_deliverable(object(), _job(), object())
    assert repairs == 2
    assert progress_updates == sorted(progress_updates)


async def test_heartbeat_stops_work_when_cancellation_wins(monkeypatch) -> None:
    session = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    monkeypatch.setattr(
        executor,
        "heartbeat_deliverable_job",
        AsyncMock(return_value=None),
    )

    with pytest.raises(executor.DeliverableJobCancellationError):
        await executor._heartbeat(session, 7, "rendering", 65)

    session.rollback.assert_awaited_once()
    session.commit.assert_not_awaited()


async def test_save_requires_current_verification_receipt(monkeypatch) -> None:
    saved = False

    async def missing_receipt(*_args, **_kwargs):
        raise ValueError("Verify this file again before presenting it")

    async def save(*_args, **_kwargs):
        nonlocal saved
        saved = True

    monkeypatch.setattr(executor, "read_receipt", missing_receipt)
    monkeypatch.setattr(executor, "save_artifact", save)

    with pytest.raises(ValueError, match="Verify this file"):
        await executor._save_verified(
            object(),
            FakeSandboxSession(),
            job=_job(),
            request=executor.VideoJobRequestV1.model_validate(_job().request),
            authored=_authored(),
            output_path="/workspace/deliverable-job-7.mp4",
        )
    assert saved is False
