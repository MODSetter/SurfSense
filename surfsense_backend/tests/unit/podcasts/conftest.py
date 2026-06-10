"""Shared builders for podcast unit tests.

These tests exercise the podcast domain through its public interfaces. The only
test double is a minimal stand-in for the SQLAlchemy ``AsyncSession`` — a real
system boundary — so the service's own repository and state machine run for
real. Briefs and transcripts are built with valid factories so each test states
just the fields it cares about.
"""

from __future__ import annotations

import pytest

from app.podcasts.schemas import (
    DurationTarget,
    PodcastSpec,
    PodcastStyle,
    SpeakerRole,
    SpeakerSpec,
    Transcript,
    TranscriptTurn,
)


class FakeAsyncSession:
    """A no-op stand-in for ``AsyncSession`` at the persistence boundary.

    The service flushes to assign state within a unit of work; in a unit test
    there is no database, so ``add``/``flush`` simply do nothing. Behavior is
    observed through the returned aggregate, never through this double.
    """

    def add(self, _obj: object) -> None:
        return None

    async def flush(self) -> None:
        return None


class FakeCeleryDbSession(FakeAsyncSession):
    """An async-context session double for Celery task bodies.

    Task bodies open ``get_celery_session_maker()()`` as an async context,
    ``get`` the row, then ``commit``. This holds one preloaded podcast and
    records whether the body committed, so tests assert on the row's final
    state — not on the calls made to get there.
    """

    def __init__(self, podcast: object | None = None) -> None:
        self._podcast = podcast
        self.committed = False

    async def get(self, _model: object, _id: object) -> object | None:
        return self._podcast

    async def commit(self) -> None:
        self.committed = True

    async def __aenter__(self) -> FakeCeleryDbSession:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        return None


@pytest.fixture
def fake_session() -> FakeAsyncSession:
    return FakeAsyncSession()


@pytest.fixture
def make_celery_session():
    """Factory for a Celery-style session double holding one podcast."""

    def _make(podcast: object | None = None) -> FakeCeleryDbSession:
        return FakeCeleryDbSession(podcast)

    return _make


@pytest.fixture
def session_maker_for():
    """Build a ``get_celery_session_maker`` replacement bound to one session.

    ``get_celery_session_maker()()`` must yield the session, so the replacement
    is a zero-arg callable returning a maker that returns the session.
    """

    def _make(session: object):
        return lambda: (lambda: session)

    return _make


@pytest.fixture
def make_spec():
    """Factory for a valid :class:`PodcastSpec`; override only what matters."""

    def _make(
        *,
        language: str = "en",
        style: PodcastStyle = PodcastStyle.CONVERSATIONAL,
        speakers: list[SpeakerSpec] | None = None,
        min_minutes: int = 10,
        max_minutes: int = 20,
        focus: str | None = None,
    ) -> PodcastSpec:
        if speakers is None:
            speakers = [
                SpeakerSpec(
                    slot=0, name="Host", role=SpeakerRole.HOST, voice_id="kokoro:am_adam"
                ),
                SpeakerSpec(
                    slot=1,
                    name="Guest",
                    role=SpeakerRole.GUEST,
                    voice_id="kokoro:af_bella",
                ),
            ]
        return PodcastSpec(
            language=language,
            style=style,
            speakers=speakers,
            duration=DurationTarget(min_minutes=min_minutes, max_minutes=max_minutes),
            focus=focus,
        )

    return _make


@pytest.fixture
def make_transcript():
    """Factory for a valid :class:`Transcript`."""

    def _make(turns: list[tuple[int, str]] | None = None) -> Transcript:
        if turns is None:
            turns = [(0, "Welcome to the show."), (1, "Glad to be here.")]
        return Transcript(
            turns=[TranscriptTurn(speaker=slot, text=text) for slot, text in turns]
        )

    return _make
