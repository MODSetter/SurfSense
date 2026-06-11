"""Podcast API + task integration fixtures.

The app's DB session and current-user dependencies ride the test's transactional
`db_session`, so seeded rows and rows touched through the endpoints (or the task
bodies) share one transaction that rolls back per test. Only true externals are
faked: the Celery broker (`*_task.delay`) is captured instead of dispatched, the
object store is a tiny in-memory backend, the Celery tasks' own session maker is
bound to the test transaction, and — for the render task — the TTS provider and
the FFmpeg merge are stubbed. `TTS_SERVICE` is pinned so the deterministic brief
proposal can resolve voices.
"""

from __future__ import annotations

import contextlib
import uuid
from collections.abc import AsyncGenerator, AsyncIterator
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.app import app, limiter
from app.config import config as app_config
from app.db import SearchSpace, User, get_async_session
from app.routes.search_spaces_routes import create_default_roles_and_membership
from app.podcasts.persistence import Podcast, PodcastStatus
from app.podcasts.schemas import (
    DurationTarget,
    PodcastSpec,
    PodcastStyle,
    SpeakerRole,
    SpeakerSpec,
    Transcript,
    TranscriptTurn,
)
from app.podcasts.service import PodcastService
from app.podcasts.tts import SynthesisRequest, SynthesizedAudio, TextToSpeech
from app.users import current_active_user

pytestmark = pytest.mark.integration

limiter.enabled = False


@pytest_asyncio.fixture
async def client(
    db_session: AsyncSession,
    db_user: User,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    async def override_user() -> User:
        return db_user

    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_async_session] = override_session
    app.dependency_overrides[current_active_user] = override_user

    try:
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            timeout=30.0,
            follow_redirects=False,
        ) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)


@pytest.fixture(autouse=True)
def tts_service(monkeypatch) -> str:
    """Pin a provider with language-agnostic voices so brief proposal resolves."""
    service = "openai/tts-1"
    monkeypatch.setattr(app_config, "TTS_SERVICE", service)
    return service


class CapturedTasks:
    """Records the args each podcast Celery task was enqueued with."""

    def __init__(self) -> None:
        self.draft: list[tuple] = []
        self.render: list[tuple] = []


@pytest.fixture(autouse=True)
def captured_tasks(monkeypatch) -> CapturedTasks:
    """Capture `*_task.delay` instead of hitting the broker (a boundary)."""
    captured = CapturedTasks()
    from app.podcasts.tasks import draft_transcript_task, render_audio_task

    monkeypatch.setattr(
        draft_transcript_task, "delay", lambda *a, **k: captured.draft.append((a, k))
    )
    monkeypatch.setattr(
        render_audio_task, "delay", lambda *a, **k: captured.render.append((a, k))
    )
    return captured


class FakeStorageBackend:
    """In-memory object store standing in for the real audio backend."""

    backend_name = "memory"

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.deleted: list[str] = []

    async def put(self, key: str, data: bytes, content_type: str | None = None) -> None:
        self.objects[key] = data

    async def open_stream(self, key: str) -> AsyncIterator[bytes]:
        yield self.objects.get(key, b"audio-bytes")

    async def delete(self, key: str) -> None:
        self.deleted.append(key)


@pytest.fixture
def fake_storage(monkeypatch) -> FakeStorageBackend:
    """Route audio storage to an in-memory backend for the stream routes."""
    backend = FakeStorageBackend()
    monkeypatch.setattr(
        "app.podcasts.storage.get_storage_backend", lambda: backend
    )
    monkeypatch.setattr(
        "app.file_storage.factory.get_storage_backend", lambda: backend
    )
    return backend


@pytest.fixture
def bind_task_session(db_session: AsyncSession, monkeypatch) -> AsyncSession:
    """Bind the Celery tasks' own session maker to the test transaction.

    Task bodies open ``get_celery_session_maker()()`` rather than receiving a
    session, so this hands them the test's session without closing it on exit; a
    task's ``commit()`` then releases a savepoint and the per-test rollback still
    cleans up.
    """

    def _make_session():
        @contextlib.asynccontextmanager
        async def _ctx() -> AsyncIterator[AsyncSession]:
            yield db_session

        return _ctx()

    for module in (
        "app.podcasts.tasks.draft",
        "app.podcasts.tasks.render",
        "app.podcasts.tasks.runtime",
    ):
        monkeypatch.setattr(
            f"{module}.get_celery_session_maker", lambda: _make_session
        )
    return db_session


class FakeTextToSpeech(TextToSpeech):
    """In-memory TTS provider: every segment yields fixed bytes (the boundary).

    Records each request so tests can assert how often synthesis was paid for.
    """

    def __init__(self) -> None:
        self.requests: list[SynthesisRequest] = []

    @property
    def container(self) -> str:
        return "mp3"

    async def synthesize(self, request: SynthesisRequest) -> SynthesizedAudio:
        self.requests.append(request)
        return SynthesizedAudio(data=b"segment-audio", container="mp3")


@pytest.fixture
def fake_tts(monkeypatch) -> FakeTextToSpeech:
    """Stand in for the configured TTS provider in the render task."""
    provider = FakeTextToSpeech()
    monkeypatch.setattr(
        "app.podcasts.tasks.render.get_text_to_speech", lambda: provider
    )
    return provider


@pytest.fixture
def fake_merge(monkeypatch) -> None:
    """Stub the FFmpeg merge (an external binary) to emit a fixed MP3."""

    async def _merge(segment_paths: list[Path], output_path: Path) -> None:
        output_path.write_bytes(b"merged-audio")

    monkeypatch.setattr("app.podcasts.rendering.renderer.concat_to_mp3", _merge)


def build_spec(
    *,
    language: str = "en",
    voice_ids: tuple[str, str] = ("openai:alloy", "openai:nova"),
) -> PodcastSpec:
    """A valid two-speaker brief; tests override only what they assert on."""
    return PodcastSpec(
        language=language,
        style=PodcastStyle.CONVERSATIONAL,
        speakers=[
            SpeakerSpec(slot=0, name="Host", role=SpeakerRole.HOST, voice_id=voice_ids[0]),
            SpeakerSpec(slot=1, name="Guest", role=SpeakerRole.GUEST, voice_id=voice_ids[1]),
        ],
        duration=DurationTarget(min_minutes=10, max_minutes=20),
    )


def build_transcript() -> Transcript:
    return Transcript(
        turns=[
            TranscriptTurn(speaker=0, text="Welcome to the show."),
            TranscriptTurn(speaker=1, text="Glad to be here."),
        ]
    )


@pytest.fixture
def make_podcast(db_session: AsyncSession):
    """Create a podcast advanced to a target lifecycle state via the service.

    Setup runs through the same public service the API uses, on the test's
    session, so the endpoint under test reads a realistically-built row.
    """

    _LADDER = [
        PodcastStatus.AWAITING_BRIEF,
        PodcastStatus.DRAFTING,
        PodcastStatus.RENDERING,
        PodcastStatus.READY,
    ]

    async def _make(
        *,
        search_space_id: int,
        status: PodcastStatus = PodcastStatus.AWAITING_BRIEF,
        title: str = "Test Podcast",
        thread_id: int | None = None,
    ) -> Podcast:
        service = PodcastService(db_session)
        podcast = await service.create(
            title=title, search_space_id=search_space_id, thread_id=thread_id
        )
        if status is PodcastStatus.PENDING:
            await db_session.flush()
            return podcast

        targets = _LADDER[: _LADDER.index(status) + 1]
        for target in targets:
            if target is PodcastStatus.AWAITING_BRIEF:
                await service.attach_brief(podcast, build_spec())
            elif target is PodcastStatus.DRAFTING:
                await service.begin_drafting(podcast)
            elif target is PodcastStatus.RENDERING:
                await service.attach_transcript(podcast, build_transcript())
            elif target is PodcastStatus.READY:
                await service.attach_audio(
                    podcast,
                    storage_backend="memory",
                    storage_key="podcasts/audio.mp3",
                    duration_seconds=123,
                )
        await db_session.flush()
        return podcast

    return _make


@pytest.fixture
def act_as():
    """Switch the authenticated user for subsequent requests on ``client``.

    The ``client`` fixture installs db_user and restores the prior overrides on
    teardown, so re-pointing the auth dependency here is undone per test.
    """

    def _act(user: User) -> None:
        app.dependency_overrides[current_active_user] = lambda: user

    return _act


@pytest_asyncio.fixture
async def db_other_user(db_session: AsyncSession) -> User:
    """A second user who is not a member of ``db_search_space``."""
    user = User(
        id=uuid.uuid4(),
        email="stranger@surfsense.net",
        hashed_password="hashed",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def foreign_podcast(
    db_session: AsyncSession, db_other_user: User, make_podcast
) -> Podcast:
    """A podcast in a space owned by the other user, invisible to db_user."""
    space = SearchSpace(name="Stranger Space", user_id=db_other_user.id)
    db_session.add(space)
    await db_session.flush()
    await create_default_roles_and_membership(db_session, space.id, db_other_user.id)
    await db_session.flush()
    return await make_podcast(search_space_id=space.id, title="Foreign")
