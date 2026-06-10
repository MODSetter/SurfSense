"""The podcast lifecycle authority: every status change goes through here.

The service owns the state machine. Each method names a real lifecycle step,
validates it against the allowed-transition table, and (de)serializes the brief
and transcript to/from their JSONB columns. It deliberately does not enqueue
Celery work — callers transition the row here, then schedule the next task — so
the rules stay testable and free of task-queue coupling.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.podcasts.persistence import Podcast, PodcastRepository, PodcastStatus
from app.podcasts.schemas import PodcastSpec, Transcript

_MAX_ERROR_CHARS = 2000

# The only status changes the machine permits. Terminal states have no exits.
_ALLOWED: dict[PodcastStatus, frozenset[PodcastStatus]] = {
    PodcastStatus.PENDING: frozenset(
        {PodcastStatus.AWAITING_BRIEF, PodcastStatus.FAILED, PodcastStatus.CANCELLED}
    ),
    PodcastStatus.AWAITING_BRIEF: frozenset(
        {PodcastStatus.DRAFTING, PodcastStatus.FAILED, PodcastStatus.CANCELLED}
    ),
    PodcastStatus.DRAFTING: frozenset(
        {PodcastStatus.AWAITING_REVIEW, PodcastStatus.FAILED, PodcastStatus.CANCELLED}
    ),
    PodcastStatus.AWAITING_REVIEW: frozenset(
        {
            PodcastStatus.RENDERING,  # approve
            PodcastStatus.DRAFTING,  # regenerate
            PodcastStatus.FAILED,
            PodcastStatus.CANCELLED,
        }
    ),
    PodcastStatus.RENDERING: frozenset(
        {PodcastStatus.READY, PodcastStatus.FAILED, PodcastStatus.CANCELLED}
    ),
    PodcastStatus.READY: frozenset(),
    PodcastStatus.FAILED: frozenset(),
    PodcastStatus.CANCELLED: frozenset(),
}


class PodcastError(RuntimeError):
    """Base class for lifecycle errors."""


class InvalidTransition(PodcastError):
    """A requested status change is not permitted from the current state."""


class SpecConflict(PodcastError):
    """A spec edit raced another: the expected version is stale."""

    def __init__(self, expected: int, actual: int) -> None:
        super().__init__(
            f"spec version conflict: expected {expected}, current is {actual}"
        )
        self.expected = expected
        self.actual = actual


class PreconditionFailed(PodcastError):
    """A transition's data precondition (brief/transcript present) is unmet."""


class PodcastService:
    """Drives one podcast through its lifecycle within a single session."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = PodcastRepository(session)

    async def create(
        self, *, title: str, search_space_id: int, thread_id: int | None = None
    ) -> Podcast:
        """Create a fresh podcast in ``PENDING`` awaiting its brief."""
        podcast = Podcast(
            title=title,
            search_space_id=search_space_id,
            thread_id=thread_id,
            status=PodcastStatus.PENDING,
            spec_version=1,
        )
        return await self._repo.add(podcast)

    async def attach_brief(self, podcast: Podcast, spec: PodcastSpec) -> Podcast:
        """Record the proposed brief and open the review gate."""
        self._transition(podcast, PodcastStatus.AWAITING_BRIEF)
        podcast.spec = spec.model_dump(mode="json")
        await self._session.flush()
        return podcast

    async def update_spec(
        self, podcast: Podcast, spec: PodcastSpec, expected_version: int
    ) -> Podcast:
        """Edit the brief at the gate, guarded by optimistic concurrency."""
        if _status(podcast) is not PodcastStatus.AWAITING_BRIEF:
            raise InvalidTransition(
                f"the brief can only be edited while awaiting_brief, "
                f"not {_status(podcast).value}"
            )
        if expected_version != podcast.spec_version:
            raise SpecConflict(expected_version, podcast.spec_version)
        podcast.spec = spec.model_dump(mode="json")
        podcast.spec_version += 1
        await self._session.flush()
        return podcast

    async def begin_drafting(self, podcast: Podcast) -> Podcast:
        """Approve the brief and start transcript drafting."""
        if podcast.spec is None:
            raise PreconditionFailed("cannot draft without a brief")
        self._transition(podcast, PodcastStatus.DRAFTING)
        await self._session.flush()
        return podcast

    async def attach_transcript(
        self, podcast: Podcast, transcript: Transcript
    ) -> Podcast:
        """Record the drafted transcript and open the go/no-go gate."""
        self._transition(podcast, PodcastStatus.AWAITING_REVIEW)
        podcast.podcast_transcript = transcript.model_dump(mode="json")
        await self._session.flush()
        return podcast

    async def approve(self, podcast: Podcast) -> Podcast:
        """Accept the transcript and start rendering."""
        if not podcast.podcast_transcript:
            raise PreconditionFailed("cannot render without a transcript")
        self._transition(podcast, PodcastStatus.RENDERING)
        await self._session.flush()
        return podcast

    async def regenerate(self, podcast: Podcast) -> Podcast:
        """Reject the transcript and draft a new one."""
        self._transition(podcast, PodcastStatus.DRAFTING)
        await self._session.flush()
        return podcast

    async def attach_audio(
        self,
        podcast: Podcast,
        *,
        storage_backend: str,
        storage_key: str,
        duration_seconds: int | None = None,
    ) -> Podcast:
        """Record rendered audio and mark the podcast ready."""
        self._transition(podcast, PodcastStatus.READY)
        podcast.storage_backend = storage_backend
        podcast.storage_key = storage_key
        podcast.duration_seconds = duration_seconds
        podcast.error = None
        await self._session.flush()
        return podcast

    async def fail(self, podcast: Podcast, error: str) -> Podcast:
        """Move a non-terminal podcast to ``FAILED`` with a reason."""
        self._transition(podcast, PodcastStatus.FAILED)
        podcast.error = (error or "")[:_MAX_ERROR_CHARS] or None
        await self._session.flush()
        return podcast

    async def cancel(self, podcast: Podcast) -> Podcast:
        """Cancel a non-terminal podcast at the user's request."""
        self._transition(podcast, PodcastStatus.CANCELLED)
        await self._session.flush()
        return podcast

    def _transition(self, podcast: Podcast, target: PodcastStatus) -> None:
        current = _status(podcast)
        if target not in _ALLOWED[current]:
            raise InvalidTransition(
                f"{current.value} -> {target.value} is not allowed"
            )
        podcast.status = target


def _status(podcast: Podcast) -> PodcastStatus:
    return PodcastStatus(podcast.status)


def read_spec(podcast: Podcast) -> PodcastSpec | None:
    """Deserialize the stored brief, or ``None`` if not yet proposed."""
    return PodcastSpec.model_validate(podcast.spec) if podcast.spec else None


def read_transcript(podcast: Podcast) -> Transcript | None:
    """Deserialize the stored transcript, or ``None`` if not yet drafted."""
    if not podcast.podcast_transcript:
        return None
    return Transcript.model_validate(podcast.podcast_transcript)


def preferences_from(podcast: Podcast | None) -> tuple[str | None, list[str]]:
    """Extract reusable (language, voice_ids) defaults from a prior podcast."""
    spec = read_spec(podcast) if podcast is not None else None
    if spec is None:
        return None, []
    return spec.language, [speaker.voice_id for speaker in spec.speakers]
