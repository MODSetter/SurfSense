"""Unit tests for podcast Celery task billing integration.

Validates ``_generate_content_podcast`` correctly wraps
``podcaster_graph.ainvoke`` in a ``billable_call`` envelope, propagates the
search-space owner's billing decision, and degrades cleanly when the
resolver fails or premium credit is exhausted.

Coverage:

* Happy-path free config: resolver → ``billable_call`` enters with
  ``usage_type='podcast_generation'`` and the configured reserve override,
  graph runs, podcast row flips to ``READY``.
* Happy-path premium config: same wiring with ``billing_tier='premium'``.
* Quota denial: ``billable_call`` raises ``QuotaInsufficientError`` →
  graph is *not* invoked, podcast row flips to ``FAILED``, return dict
  carries ``reason='premium_quota_exhausted'``.
* Resolver failure: ``ValueError`` from the resolver → podcast row flips
  to ``FAILED``, return dict carries ``reason='billing_resolution_failed'``.
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
    def __init__(self, podcast):
        self._podcast = podcast
        self.commit_count = 0

    async def execute(self, _stmt):
        return _FakeExecResult(self._podcast)

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


def _make_podcast(podcast_id: int = 7, thread_id: int = 99) -> SimpleNamespace:
    """Stand-in for a ``Podcast`` row. Importing ``PodcastStatus`` lazily
    inside helpers keeps this fixture cheap."""
    return SimpleNamespace(
        id=podcast_id,
        title="Test Podcast",
        thread_id=thread_id,
        status=None,
        podcast_transcript=None,
        file_location=None,
    )


@contextlib.asynccontextmanager
async def _ok_billable_call(**kwargs):
    """Stand-in for ``billable_call`` that records its kwargs and yields a
    no-op accumulator-shaped object."""
    _CALL_LOG.append(kwargs)
    yield SimpleNamespace()


_CALL_LOG: list[dict[str, Any]] = []


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
    yield SimpleNamespace()  # pragma: no cover — for grammar only


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
    """Happy path: free billing tier still wraps the graph call so the
    audit row is recorded. Verifies kwargs threading."""
    from app.config import config as app_config
    from app.db import PodcastStatus
    from app.tasks.celery_tasks import podcast_tasks

    podcast = _make_podcast(podcast_id=7, thread_id=99)
    session = _FakeSession(podcast)
    monkeypatch.setattr(
        podcast_tasks,
        "get_celery_session_maker",
        lambda: _FakeSessionMaker(session),
    )

    user_id = uuid4()

    async def _fake_resolver(sess, search_space_id, *, thread_id=None):
        assert search_space_id == 555
        assert thread_id == 99
        return user_id, "free", "openrouter/some-free-model"

    monkeypatch.setattr(
        podcast_tasks, "_resolve_agent_billing_for_search_space", _fake_resolver
    )
    monkeypatch.setattr(podcast_tasks, "billable_call", _ok_billable_call)

    async def _fake_graph_invoke(state, config):
        return {
            "podcast_transcript": [
                SimpleNamespace(speaker_id=0, dialog="Hi"),
                SimpleNamespace(speaker_id=1, dialog="Hello"),
            ],
            "final_podcast_file_path": "/tmp/podcast.wav",
        }

    monkeypatch.setattr(podcast_tasks.podcaster_graph, "ainvoke", _fake_graph_invoke)

    result = await podcast_tasks._generate_content_podcast(
        podcast_id=7,
        source_content="hello world",
        search_space_id=555,
        user_prompt="make it short",
    )

    assert result["status"] == "ready"
    assert result["podcast_id"] == 7
    assert podcast.status == PodcastStatus.READY
    assert podcast.file_location == "/tmp/podcast.wav"

    assert len(_CALL_LOG) == 1
    call = _CALL_LOG[0]
    assert call["user_id"] == user_id
    assert call["search_space_id"] == 555
    assert call["billing_tier"] == "free"
    assert call["base_model"] == "openrouter/some-free-model"
    assert call["usage_type"] == "podcast_generation"
    assert (
        call["quota_reserve_micros_override"]
        == app_config.QUOTA_DEFAULT_PODCAST_RESERVE_MICROS
    )
    assert call["thread_id"] == 99
    assert call["call_details"] == {"podcast_id": 7, "title": "Test Podcast"}


@pytest.mark.asyncio
async def test_billable_call_invoked_with_premium_tier(monkeypatch):
    """Premium resolution flows through to ``billable_call`` so the
    reserve/finalize path triggers."""
    from app.tasks.celery_tasks import podcast_tasks

    podcast = _make_podcast()
    session = _FakeSession(podcast)
    monkeypatch.setattr(
        podcast_tasks,
        "get_celery_session_maker",
        lambda: _FakeSessionMaker(session),
    )

    user_id = uuid4()

    async def _fake_resolver(sess, search_space_id, *, thread_id=None):
        return user_id, "premium", "gpt-5.4"

    monkeypatch.setattr(
        podcast_tasks, "_resolve_agent_billing_for_search_space", _fake_resolver
    )
    monkeypatch.setattr(podcast_tasks, "billable_call", _ok_billable_call)

    async def _fake_graph_invoke(state, config):
        return {"podcast_transcript": [], "final_podcast_file_path": "x.wav"}

    monkeypatch.setattr(podcast_tasks.podcaster_graph, "ainvoke", _fake_graph_invoke)

    await podcast_tasks._generate_content_podcast(
        podcast_id=7,
        source_content="hi",
        search_space_id=555,
        user_prompt=None,
    )

    assert _CALL_LOG[0]["billing_tier"] == "premium"
    assert _CALL_LOG[0]["base_model"] == "gpt-5.4"


@pytest.mark.asyncio
async def test_quota_insufficient_marks_podcast_failed_and_skips_graph(monkeypatch):
    """When ``billable_call`` denies the reservation, the graph never
    runs and the podcast row flips to FAILED with the documented reason
    code."""
    from app.db import PodcastStatus
    from app.tasks.celery_tasks import podcast_tasks

    podcast = _make_podcast(podcast_id=8)
    session = _FakeSession(podcast)
    monkeypatch.setattr(
        podcast_tasks,
        "get_celery_session_maker",
        lambda: _FakeSessionMaker(session),
    )

    async def _fake_resolver(sess, search_space_id, *, thread_id=None):
        return uuid4(), "premium", "gpt-5.4"

    monkeypatch.setattr(
        podcast_tasks, "_resolve_agent_billing_for_search_space", _fake_resolver
    )
    monkeypatch.setattr(podcast_tasks, "billable_call", _denying_billable_call)

    graph_invoked = []

    async def _fake_graph_invoke(state, config):
        graph_invoked.append(True)
        return {}

    monkeypatch.setattr(podcast_tasks.podcaster_graph, "ainvoke", _fake_graph_invoke)

    result = await podcast_tasks._generate_content_podcast(
        podcast_id=8,
        source_content="hi",
        search_space_id=555,
        user_prompt=None,
    )

    assert result == {
        "status": "failed",
        "podcast_id": 8,
        "reason": "premium_quota_exhausted",
    }
    assert podcast.status == PodcastStatus.FAILED
    assert graph_invoked == []  # Graph never ran on denied reservation.


@pytest.mark.asyncio
async def test_resolver_failure_marks_podcast_failed(monkeypatch):
    """If the resolver raises (e.g. search-space deleted), the task fails
    cleanly without invoking the graph."""
    from app.db import PodcastStatus
    from app.tasks.celery_tasks import podcast_tasks

    podcast = _make_podcast(podcast_id=9)
    session = _FakeSession(podcast)
    monkeypatch.setattr(
        podcast_tasks,
        "get_celery_session_maker",
        lambda: _FakeSessionMaker(session),
    )

    async def _failing_resolver(sess, search_space_id, *, thread_id=None):
        raise ValueError("Search space 555 not found")

    monkeypatch.setattr(
        podcast_tasks, "_resolve_agent_billing_for_search_space", _failing_resolver
    )

    graph_invoked = []

    async def _fake_graph_invoke(state, config):
        graph_invoked.append(True)
        return {}

    monkeypatch.setattr(podcast_tasks.podcaster_graph, "ainvoke", _fake_graph_invoke)

    result = await podcast_tasks._generate_content_podcast(
        podcast_id=9,
        source_content="hi",
        search_space_id=555,
        user_prompt=None,
    )

    assert result == {
        "status": "failed",
        "podcast_id": 9,
        "reason": "billing_resolution_failed",
    }
    assert podcast.status == PodcastStatus.FAILED
    assert graph_invoked == []
