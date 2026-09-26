"""Podcast voices from the bundled audio.cpp server, one request per turn."""

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass

import httpx

from modules.llm.catalog.local.engines.audiocpp.manifest_fields import AudioDefaults
from modules.llm.hardware import system_memory
from modules.llm.providers.audiocpp.joined_wav import joined_wav
from modules.llm.providers.audiocpp.memory import (
    NotEnoughMemoryError,
    OtherModel,
    check_voicing_memory,
)
from modules.llm.providers.llamacpp import RouterClient
from modules.llm.providers.protocols import SpokenTurn, SynthesizedAudio, Voice

__all__ = [
    "AudioCppSpeech",
    "NotEnoughMemoryError",
    "OtherModel",
    "VoicedModel",
    "VoicingError",
]

logger = logging.getLogger(__name__)

# A turn voices in seconds on the CPU; a load adds a second or two.
_TURN_TIMEOUT = httpx.Timeout(600, connect=10)

# Memory the app gives back arrives within this: Electron stops sd-server on its
# next 5 s poll once no image job needs it, and a chat worker exits within a
# second of its unload.
MEMORY_WAIT_SECONDS = 10.0
MEMORY_POLL_SECONDS = 1.0


class VoicingError(Exception):
    """The server was reached and failed a turn; the message is its own."""


@dataclass(frozen=True)
class VoicedModel:
    """An installed audio model: the id the server knows it by, and its entry."""

    model_id: str
    audio: AudioDefaults
    # The other curated audio models, most preferred first, for a refusal to name.
    others: tuple[OtherModel, ...] = ()


class AudioCppSpeech:
    def __init__(
        self,
        model: VoicedModel,
        *,
        base_url: str,
        chat_runtime: RouterClient,
        transport: httpx.AsyncBaseTransport | None = None,
        available: Callable[[], int] | None = None,
    ) -> None:
        self._model = model
        self._base_url = base_url
        self._chat_runtime = chat_runtime
        self._transport = transport
        # Read when checked, not when built: memory moves while a job drafts.
        self._available = available or (lambda: system_memory.available_bytes())

    def voices(self) -> list[Voice]:
        """The model's roster. A voice with no language speaks all the model's."""
        every = tuple(self._model.audio.languages)
        return [
            Voice(v.id, v.label, v.gender, (v.language,) if v.language else every)
            for v in self._model.audio.voices
        ]

    async def check_memory(self) -> None:
        """Before anything loads: once loaded, the model takes its peak. Short,
        it frees the chat model first, as voicing will; drafting reloads it."""
        try:
            await self._wait_for_memory(0)
        except NotEnoughMemoryError:
            await _free_chat_model(self._chat_runtime)
            await self._wait_for_memory(MEMORY_WAIT_SECONDS)

    async def synthesize(
        self, turns: list[SpokenTurn], language: str
    ) -> SynthesizedAudio:
        # The script is written, so the chat model's memory is voicing's now.
        await _free_chat_model(self._chat_runtime)
        await self._wait_for_memory(MEMORY_WAIT_SECONDS)
        speaks = {voice.id: voice.languages for voice in self.voices()}
        async with httpx.AsyncClient(
            base_url=self._base_url, timeout=_TURN_TIMEOUT, transport=self._transport
        ) as client:
            try:
                voiced = await self._voice_each(client, turns, language, speaks)
            finally:
                await _unload(client)
        return SynthesizedAudio(joined_wav(voiced), "audio/wav")

    async def _wait_for_memory(self, seconds: float) -> None:
        deadline = time.monotonic() + seconds
        while True:
            try:
                return check_voicing_memory(
                    self._model.audio.peak_mb, self._available(), self._model.others
                )
            except NotEnoughMemoryError:
                if time.monotonic() >= deadline:
                    raise
            await asyncio.sleep(MEMORY_POLL_SECONDS)

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
            if reply.is_error:
                raise VoicingError(
                    f"audio.cpp could not voice turn {index} of {len(turns)}: "
                    f"{_server_message(reply)}"
                )
            voiced.append(reply.content)
        return voiced


def _server_message(reply: httpx.Response) -> str:
    """audio.cpp answers a failure with {"error": {"message": ...}}."""
    try:
        return str(reply.json()["error"]["message"])
    except (ValueError, KeyError, TypeError):
        return f"HTTP {reply.status_code}"


async def _free_chat_model(router: RouterClient) -> None:
    """The router reloads it on its next request. A failure only costs the
    memory check its margin, not the minutes of drafting behind it."""
    try:
        for resident in await router.models():
            if resident.loaded:
                await router.unload(resident.id)
    except httpx.HTTPError:
        logger.warning("audiocpp: could not unload the chat model", exc_info=True)


async def _unload(client: httpx.AsyncClient) -> None:
    """Give the model's memory back; the idle timer is only the backstop."""
    try:
        (await client.post("/v1/tasks/unload_all_models")).raise_for_status()
    except httpx.HTTPError:
        logger.warning("audiocpp: could not unload; the idle timer will", exc_info=True)
