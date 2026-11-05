"""Podcast voices from ElevenLabs' own route, one request per line."""

import asyncio
import logging
import wave
from urllib.parse import quote

import httpx

from modules.llm.providers.elevenlabs.refusal import refusal_message
from modules.llm.providers.openai_compatible.joined_replies import joined_replies
from modules.llm.providers.openai_compatible.speech import NonRetryableSpeechError
from modules.llm.providers.protocols import SpokenTurn, SynthesizedAudio
from shared import cancellation

__all__ = ["ElevenLabsSpeech"]

logger = logging.getLogger(__name__)

LINE_TIMEOUT = httpx.Timeout(120.0, connect=10.0)
# WAV, because only WAV takes a pause between speakers; 44.1 kHz needs a Pro plan.
_OUTPUT_FORMAT = "wav_24000"
# A concurrency refusal comes at once and bills nothing, with no Retry-After. Free
# allows two v4 requests at a time, and Studio runs four jobs. A 5xx is not repeated:
# the audio may already be billed.
_BACKOFF_SECONDS = (1, 2, 4, 8)


class ElevenLabsSpeech:
    def __init__(
        self,
        model: str,
        *,
        base_url: str,
        api_key: str | None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._transport = transport

    async def check_memory(self) -> None:
        """ElevenLabs voices it, so nothing here has to fit."""

    async def synthesize(
        self, turns: list[SpokenTurn], language: str
    ) -> SynthesizedAudio:
        spoken = [turn for turn in turns if turn.text.strip()]
        voiced = []
        cost = 0
        async with httpx.AsyncClient(
            timeout=LINE_TIMEOUT,
            headers={"xi-api-key": self._api_key} if self._api_key else {},
            transport=self._transport,
        ) as client:
            for index, turn in enumerate(spoken, start=1):
                reply = await self._voice(client, index, len(spoken), turn, language)
                voiced.append(reply.content)
                cost += _credits(reply)
        logger.info("elevenlabs: %s lines cost %s credits", len(spoken), cost)
        try:
            return joined_replies(voiced)
        except (wave.Error, EOFError, ValueError) as error:
            raise NonRetryableSpeechError(
                f"ElevenLabs answered, but not as WAV: {error}"
            ) from error

    async def _voice(
        self,
        client: httpx.AsyncClient,
        index: int,
        total: int,
        turn: SpokenTurn,
        language: str,
    ) -> httpx.Response:
        if not turn.voice:
            raise NonRetryableSpeechError("Choose a voice to test.")
        body = {"text": turn.text, "model_id": self._model}
        if language:
            body["language_code"] = language
        url = f"{self._base_url}/v1/text-to-speech/{quote(turn.voice, safe='')}"
        for delay in (*_BACKOFF_SECONDS, None):
            # A request in flight cannot be stopped; a line not yet sent can.
            cancellation.raise_if_cancelled()
            try:
                reply = await client.post(
                    url, params={"output_format": _OUTPUT_FORMAT}, json=body
                )
            except httpx.HTTPError as error:
                raise _failure(index, total, str(error)) from error
            if reply.status_code != 429 or delay is None:
                break
            await asyncio.sleep(delay)
        if reply.is_error:
            raise _failure(index, total, refusal_message(reply))
        return reply


def _credits(reply: httpx.Response) -> int:
    """For the log alone, from an undocumented header: the lines before it are
    already billed, so nothing here may fail the episode."""
    try:
        return int(reply.headers.get("character-cost") or 0)
    except ValueError:
        return 0


def _failure(index: int, total: int, words: str) -> NonRetryableSpeechError:
    """ "Line 1 of 1" says nothing when one line is being tried."""
    if total == 1:
        return NonRetryableSpeechError(words)
    return NonRetryableSpeechError(
        f"ElevenLabs could not voice line {index} of {total}: {words}"
    )
