"""Unit tests for video-presentation Celery task billing integration.

Mirrors ``test_podcast_billing.py`` for the video-presentation task.
Validates the same wrap-graph-in-billable_call pattern and ensures the
larger ``QUOTA_DEFAULT_VIDEO_PRESENTATION_RESERVE_MICROS`` reservation is
threaded through.

Coverage:

* Free config: graph runs, ``billable_call`` invoked with the video
  reserve override.
* Premium config: same wiring with ``billing_tier='premium'``.
* Quota denial: graph not invoked, row → FAILED, reason code surfaced.
* Resolver failure: row → FAILED with ``billing_resolution_failed``.
"""

from __future__ import annotations

import contextlib
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeExecResult:
    def __init__(self, obj):
        self._obj = obj

    def scalars(self):
        return self

    def first(self):
        return self._obj

    def filter(self, *_args, **_kwargs):
        return self


class _FakeSession:
    def __init__(self, video):
        self._video = video
        self.commit_count = 0

    async def execute(self, _stmt):
        return _FakeExecResult(self._video)

    async def commit(self):
        self.commit_count += 1

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None


class _FakeSessionMaker:
    def __init__(self, session: _FakeSession):
        self._session = session

    def __call__(self):
        return self._session


def _make_video(video_id: int = 11, thread_id: int = 99) -> SimpleNamespace:
    return SimpleNamespace(
        id=video_id,
        title="Test Presentation",
        thread_id=thread_id,
        status=None,
        slides=None,
        scene_codes=None,
    )


_CALL_LOG: list[dict[str, Any]] = []


@contextlib.asynccontextmanager
async def _ok_billable_call(**kwargs):
    _CALL_LOG.append(kwargs)
    yield SimpleNamespace()


@contextlib.asynccontextmanager
async def _denying_billable_call(**kwargs):
    from app.services.billable_calls import QuotaInsufficientError

    _CALL_LOG.append(kwargs)
    raise QuotaInsufficientError(
        usage_type=kwargs.get("usage_type", "?"),
        used_micros=5_000_000,
        limit_micros=5_000_000,
        remaining_micros=0,
    )
    yield SimpleNamespace()  # pragma: no cover


@contextlib.asynccontextmanager
async def _settlement_failing_billable_call(**kwargs):
    from app.services.billable_calls import BillingSettlementError

    _CALL_LOG.append(kwargs)
    yield SimpleNamespace()
    raise BillingSettlementError(
        usage_type=kwargs.get("usage_type", "?"),
        user_id=kwargs["user_id"],
        cause=RuntimeError("finalize failed"),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_call_log():
    _CALL_LOG.clear()
    yield
    _CALL_LOG.clear()


@pytest.mark.asyncio
async def test_billable_call_invoked_with_correct_kwargs_for_free_config(monkeypatch):
    from app.config import config as app_config
    from app.db import VideoPresentationStatus
    from app.tasks.celery_tasks import video_presentation_tasks

    video = _make_video(video_id=11, thread_id=99)
    session = _FakeSession(video)
    monkeypatch.setattr(
        video_presentation_tasks,
        "get_celery_session_maker",
        lambda: _FakeSessionMaker(session),
    )

    user_id = uuid4()

    async def _fake_resolver(sess, search_space_id, *, thread_id=None):
        assert search_space_id == 777
        assert thread_id == 99
        return user_id, "free", "openrouter/some-free-model"

    monkeypatch.setattr(
        video_presentation_tasks,
        "_resolve_agent_billing_for_search_space",
        _fake_resolver,
    )
    monkeypatch.setattr(video_presentation_tasks, "billable_call", _ok_billable_call)

    async def _fake_graph_invoke(state, config):
        return {"slides": [], "slide_audio_results": [], "slide_scene_codes": []}

    monkeypatch.setattr(
        video_presentation_tasks.video_presentation_graph,
        "ainvoke",
        _fake_graph_invoke,
    )

    result = await video_presentation_tasks._generate_video_presentation(
        video_presentation_id=11,
        source_content="content",
        search_space_id=777,
        user_prompt=None,
    )

    assert result["status"] == "ready"
    assert result["video_presentation_id"] == 11
    assert video.status == VideoPresentationStatus.READY

    assert len(_CALL_LOG) == 1
    call = _CALL_LOG[0]
    assert call["user_id"] == user_id
    assert call["search_space_id"] == 777
    assert call["billing_tier"] == "free"
    assert call["base_model"] == "openrouter/some-free-model"
    assert call["usage_type"] == "video_presentation_generation"
    assert (
        call["quota_reserve_micros_override"]
        == app_config.QUOTA_DEFAULT_VIDEO_PRESENTATION_RESERVE_MICROS
    )
    # Background artifact audit rows intentionally omit the TokenUsage.thread_id
    # FK to avoid coupling Celery audit commits to an active chat transaction.
    assert "thread_id" not in call
    assert call["call_details"] == {
        "video_presentation_id": 11,
        "title": "Test Presentation",
        "thread_id": 99,
    }
    assert callable(call["billable_session_factory"])


@pytest.mark.asyncio
async def test_billable_call_invoked_with_premium_tier(monkeypatch):
    from app.tasks.celery_tasks import video_presentation_tasks

    video = _make_video()
    session = _FakeSession(video)
    monkeypatch.setattr(
        video_presentation_tasks,
        "get_celery_session_maker",
        lambda: _FakeSessionMaker(session),
    )

    user_id = uuid4()

    async def _fake_resolver(sess, search_space_id, *, thread_id=None):
        return user_id, "premium", "gpt-5.4"

    monkeypatch.setattr(
        video_presentation_tasks,
        "_resolve_agent_billing_for_search_space",
        _fake_resolver,
    )
    monkeypatch.setattr(video_presentation_tasks, "billable_call", _ok_billable_call)

    async def _fake_graph_invoke(state, config):
        return {"slides": [], "slide_audio_results": [], "slide_scene_codes": []}

    monkeypatch.setattr(
        video_presentation_tasks.video_presentation_graph,
        "ainvoke",
        _fake_graph_invoke,
    )

    await video_presentation_tasks._generate_video_presentation(
        video_presentation_id=11,
        source_content="content",
        search_space_id=777,
        user_prompt=None,
    )

    assert _CALL_LOG[0]["billing_tier"] == "premium"
    assert _CALL_LOG[0]["base_model"] == "gpt-5.4"


@pytest.mark.asyncio
async def test_quota_insufficient_marks_video_failed_and_skips_graph(monkeypatch):
    from app.db import VideoPresentationStatus
    from app.tasks.celery_tasks import video_presentation_tasks

    video = _make_video(video_id=12)
    session = _FakeSession(video)
    monkeypatch.setattr(
        video_presentation_tasks,
        "get_celery_session_maker",
        lambda: _FakeSessionMaker(session),
    )

    async def _fake_resolver(sess, search_space_id, *, thread_id=None):
        return uuid4(), "premium", "gpt-5.4"

    monkeypatch.setattr(
        video_presentation_tasks,
        "_resolve_agent_billing_for_search_space",
        _fake_resolver,
    )
    monkeypatch.setattr(
        video_presentation_tasks, "billable_call", _denying_billable_call
    )

    graph_invoked = []

    async def _fake_graph_invoke(state, config):
        graph_invoked.append(True)
        return {}

    monkeypatch.setattr(
        video_presentation_tasks.video_presentation_graph,
        "ainvoke",
        _fake_graph_invoke,
    )

    result = await video_presentation_tasks._generate_video_presentation(
        video_presentation_id=12,
        source_content="content",
        search_space_id=777,
        user_prompt=None,
    )

    assert result == {
        "status": "failed",
        "video_presentation_id": 12,
        "reason": "premium_quota_exhausted",
    }
    assert video.status == VideoPresentationStatus.FAILED
    assert graph_invoked == []


@pytest.mark.asyncio
async def test_billing_settlement_failure_marks_video_failed(monkeypatch):
    from app.db import VideoPresentationStatus
    from app.tasks.celery_tasks import video_presentation_tasks

    video = _make_video(video_id=14)
    session = _FakeSession(video)
    monkeypatch.setattr(
        video_presentation_tasks,
        "get_celery_session_maker",
        lambda: _FakeSessionMaker(session),
    )

    async def _fake_resolver(sess, search_space_id, *, thread_id=None):
        return uuid4(), "premium", "gpt-5.4"

    monkeypatch.setattr(
        video_presentation_tasks,
        "_resolve_agent_billing_for_search_space",
        _fake_resolver,
    )
    monkeypatch.setattr(
        video_presentation_tasks,
        "billable_call",
        _settlement_failing_billable_call,
    )

    async def _fake_graph_invoke(state, config):
        return {"slides": [], "slide_audio_results": [], "slide_scene_codes": []}

    monkeypatch.setattr(
        video_presentation_tasks.video_presentation_graph,
        "ainvoke",
        _fake_graph_invoke,
    )

    result = await video_presentation_tasks._generate_video_presentation(
        video_presentation_id=14,
        source_content="content",
        search_space_id=777,
        user_prompt=None,
    )

    assert result == {
        "status": "failed",
        "video_presentation_id": 14,
        "reason": "billing_settlement_failed",
    }
    assert video.status == VideoPresentationStatus.FAILED


@pytest.mark.asyncio
async def test_resolver_failure_marks_video_failed(monkeypatch):
    from app.db import VideoPresentationStatus
    from app.tasks.celery_tasks import video_presentation_tasks

    video = _make_video(video_id=13)
    session = _FakeSession(video)
    monkeypatch.setattr(
        video_presentation_tasks,
        "get_celery_session_maker",
        lambda: _FakeSessionMaker(session),
    )

    async def _failing_resolver(sess, search_space_id, *, thread_id=None):
        raise ValueError("Search space 777 not found")

    monkeypatch.setattr(
        video_presentation_tasks,
        "_resolve_agent_billing_for_search_space",
        _failing_resolver,
    )

    graph_invoked = []

    async def _fake_graph_invoke(state, config):
        graph_invoked.append(True)
        return {}

    monkeypatch.setattr(
        video_presentation_tasks.video_presentation_graph,
        "ainvoke",
        _fake_graph_invoke,
    )

    result = await video_presentation_tasks._generate_video_presentation(
        video_presentation_id=13,
        source_content="content",
        search_space_id=777,
        user_prompt=None,
    )

    assert result == {
        "status": "failed",
        "video_presentation_id": 13,
        "reason": "billing_resolution_failed",
    }
    assert video.status == VideoPresentationStatus.FAILED
    assert graph_invoked == []
