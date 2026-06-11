"""Render an approved transcript into a single podcast audio file.

The renderer is the only place that turns dialogue into sound. It maps each
turn to its speaker's voice, synthesises segments concurrently (capped, served
from the segment cache when possible, and coalesced so identical lines render
once), then merges them in order. It takes a settled spec + transcript and
returns bytes; persistence and lifecycle transitions belong to the service.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from app.podcasts.schemas import PodcastSpec, Transcript, TranscriptTurn
from app.podcasts.tts import SynthesisRequest, TextToSpeech, TextToSpeechError
from app.podcasts.voices import VoiceCatalog

from .cache import SegmentCache
from .errors import RenderError
from .merge import concat_to_mp3

# Bounds how many segments synthesise at once. Protects hosted-provider rate
# limits and avoids thrashing the local Kokoro pipeline; the renderer is I/O- or
# model-bound per segment, so a small pool already saturates throughput.
DEFAULT_MAX_CONCURRENCY = 4

_MERGED_FILENAME = "podcast.mp3"


@dataclass(frozen=True, slots=True)
class RenderedPodcast:
    """The finished episode: encoded bytes plus their container."""

    data: bytes
    container: str


class PodcastRenderer:
    """Synthesises and merges a transcript using one TTS provider."""

    def __init__(
        self,
        *,
        tts: TextToSpeech,
        catalog: VoiceCatalog,
        max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
    ) -> None:
        self._tts = tts
        self._catalog = catalog
        self._max_concurrency = max_concurrency

    async def render(
        self,
        *,
        spec: PodcastSpec,
        transcript: Transcript,
        workdir: Path,
    ) -> RenderedPodcast:
        """Produce the merged MP3 for ``transcript`` under ``spec``.

        ``workdir`` holds the segment cache and merge output; reusing the same
        directory across renders is what makes voice edits cheap.
        """
        cache = SegmentCache(workdir / "segments")
        requests = [self._request_for(spec, turn) for turn in transcript.turns]

        # Concurrency primitives are created per render so each call is bound to
        # the event loop running it (Celery tasks may use a fresh loop).
        synthesizer = _SegmentSynthesizer(self._tts, cache, self._max_concurrency)
        segment_paths = await asyncio.gather(
            *(synthesizer.segment(request) for request in requests)
        )

        output_path = workdir / _MERGED_FILENAME
        await concat_to_mp3(list(segment_paths), output_path)
        return RenderedPodcast(data=output_path.read_bytes(), container="mp3")

    def _request_for(
        self, spec: PodcastSpec, turn: TranscriptTurn
    ) -> SynthesisRequest:
        try:
            speaker = spec.speaker_for(turn.speaker)
        except KeyError as exc:
            raise RenderError(
                f"transcript references unknown speaker slot {turn.speaker}"
            ) from exc
        try:
            voice = self._catalog.get(speaker.voice_id)
        except KeyError as exc:
            raise RenderError(f"unknown voice {speaker.voice_id!r}") from exc
        return SynthesisRequest(
            text=turn.text, voice=voice.native_ref, language=spec.language
        )


class _SegmentSynthesizer:
    """Per-render synthesis coordinator: caps concurrency and dedupes work.

    Beyond the on-disk cache (which serves cross-render reuse), this coalesces
    identical segments that race within one render so the same line is voiced
    once even when several turns request it simultaneously.
    """

    def __init__(
        self, tts: TextToSpeech, cache: SegmentCache, max_concurrency: int
    ) -> None:
        self._tts = tts
        self._cache = cache
        self._container = tts.container
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._inflight: dict[str, asyncio.Future[Path]] = {}
        self._inflight_lock = asyncio.Lock()

    async def segment(self, request: SynthesisRequest) -> Path:
        key = self._cache.key(request)
        cached = self._cache.get(key, self._container)
        if cached is not None:
            return cached

        async with self._inflight_lock:
            future = self._inflight.get(key)
            owner = future is None
            if owner:
                future = asyncio.get_event_loop().create_future()
                self._inflight[key] = future

        # The owner runs the work and publishes the outcome on the shared future;
        # every caller (owner included) reads it back via ``await future`` so the
        # result is retrieved exactly once-or-more and never left dangling.
        if owner:
            try:
                path = await self._synthesize(request, key)
            except BaseException as exc:  # noqa: BLE001 - relayed to all waiters
                future.set_exception(exc)
            else:
                future.set_result(path)
            finally:
                await self._forget(key)

        return await future

    async def _synthesize(self, request: SynthesisRequest, key: str) -> Path:
        async with self._semaphore:
            cached = self._cache.get(key, self._container)
            if cached is not None:
                return cached
            try:
                audio = await self._tts.synthesize(request)
            except TextToSpeechError as exc:
                raise RenderError(f"segment synthesis failed: {exc}") from exc
            return self._cache.put(key, audio.container, audio.data)

    async def _forget(self, key: str) -> None:
        async with self._inflight_lock:
            self._inflight.pop(key, None)
