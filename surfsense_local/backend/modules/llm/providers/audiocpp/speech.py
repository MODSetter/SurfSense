"""Podcast voices from the bundled audio.cpp server, one request per turn."""

import logging
from collections.abc import Callable
from dataclasses import dataclass

import httpx

from modules.llm.catalog.local.engines.audiocpp.manifest_fields import AudioDefaults
from modules.llm.hardware.system_memory import available_bytes
from modules.llm.providers.audiocpp.joined_wav import joined_wav
from modules.llm.providers.audiocpp.memory import (
    NotEnoughMemoryError,
    check_voicing_memory,
)
from modules.llm.providers.protocols import SpokenTurn, SynthesizedAudio, Voice

__all__ = ["AudioCppSpeech", "NotEnoughMemoryError", "VoicedModel"]

logger = logging.getLogger(__name__)

# A turn voices in seconds on the CPU; a load adds a second or two.
_TURN_TIMEOUT = httpx.Timeout(600, connect=10)


@dataclass(frozen=True)
class VoicedModel:
    """An installed audio model: the id the server knows it by, and its entry."""

    model_id: str
    audio: AudioDefaults


class AudioCppSpeech:
    def __init__(
        self,
        model: VoicedModel,
        *,
        base_url: str,
        transport: httpx.AsyncBaseTransport | None = None,
        available: Callable[[], int] = available_bytes,
    ) -> None:
        self._model = model
        self._base_url = base_url
        self._transport = transport
        self._available = available

    def voices(self) -> list[Voice]:
        """The model's roster. A voice with no language speaks all the model's."""
        every = tuple(self._model.audio.languages)
        return [
            Voice(v.id, v.label, (v.language,) if v.language else every)
            for v in self._model.audio.voices
        ]

    def check_memory(self) -> None:
        """Before anything loads: once loaded, the model takes its peak."""
        check_voicing_memory(self._model.audio.peak_mb, self._available())

    async def synthesize(
        self, turns: list[SpokenTurn], language: str
    ) -> SynthesizedAudio:
        # Again at voicing: the chat model's own memory may have moved since.
        self.check_memory()
        speaks = {voice.id: voice.languages for voice in self.voices()}
        async with httpx.AsyncClient(
            base_url=self._base_url, timeout=_TURN_TIMEOUT, transport=self._transport
        ) as client:
            try:
                voiced = await self._voice_each(client, turns, language, speaks)
            finally:
                await _unload(client)
        return SynthesizedAudio(joined_wav(voiced), "audio/wav")

    async def _voice_each(
        self,
        client: httpx.AsyncClient,
        turns: list[SpokenTurn],
        language: str,
        speaks: dict[str, tuple[str, ...]],
    ) -> list[bytes]:
        voiced = []
        for index, turn in enumerate(turns, start=1):
            logger.info(
                "audiocpp: turn %s/%s voice=%s %s chars",
                index,
                len(turns),
                turn.voice,
                len(turn.text),
            )
            request = {
                "model": self._model.model_id,
                "input": turn.text,
                "voice": turn.voice,
            }
            # Only a voice that speaks several needs telling which.
            if len(speaks.get(turn.voice, ())) > 1:
                request["language"] = language
            reply = await client.post("/v1/audio/speech", json=request)
            reply.raise_for_status()
            voiced.append(reply.content)
        return voiced


async def _unload(client: httpx.AsyncClient) -> None:
    """Give the model's memory back; the idle timer is only the backstop."""
    try:
        (await client.post("/v1/tasks/unload_all_models")).raise_for_status()
    except httpx.HTTPError:
        logger.warning("audiocpp: could not unload; the idle timer will", exc_info=True)
