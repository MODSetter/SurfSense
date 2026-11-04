"""Podcast voices from a server's /audio/speech, one request per turn."""

import logging
import wave

import httpx

from modules.llm.connections.key_headers import key_headers
from modules.llm.providers.openai_compatible.joined_replies import joined_replies
from modules.llm.providers.openai_compatible.pcm_reply import wav_from_pcm_reply
from modules.llm.providers.protocols import SpokenTurn, SynthesizedAudio
from shared import cancellation

__all__ = ["NonRetryableSpeechError", "RemoteSpeech"]

logger = logging.getLogger(__name__)

TURN_TIMEOUT = httpx.Timeout(120.0, connect=10.0)


class NonRetryableSpeechError(RuntimeError):
    """Voicing began, so repeating the job would bill the episode twice."""


class RemoteSpeech:
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
        """The server voices it, so nothing here has to fit."""

    async def synthesize(
        self, turns: list[SpokenTurn], language: str
    ) -> SynthesizedAudio:
        async with httpx.AsyncClient(
            timeout=TURN_TIMEOUT,
            headers=key_headers(self._base_url, self._api_key),
            transport=self._transport,
        ) as client:
            voiced = []
            # WAV first, because only WAV takes a pause between speakers; pcm
            # becomes one where its header states the rate. OpenRouter takes
            # only mp3 or pcm, and refuses wav before it reads the key or voice.
            chosen = "wav"
            for index, turn in enumerate(turns, start=1):
                reply = await self._voice(client, index, len(turns), turn, chosen)
                if reply.is_error and index == 1:
                    # Asked once, on the first line: a refusal after it is
                    # that line's own, not the format's.
                    chosen = "pcm"
                    reply = await self._voice(client, index, len(turns), turn, chosen)
                    if reply.is_error or wav_from_pcm_reply(reply) is None:
                        chosen = "mp3"
                        reply = await self._voice(
                            client, index, len(turns), turn, chosen
                        )
                if reply.is_error:
                    raise NonRetryableSpeechError(
                        f"the server could not voice turn {index} of {len(turns)}: "
                        f"{_server_message(reply)}"
                    )
                voiced.append(
                    _line_as_wav(reply, index, len(turns))
                    if chosen == "pcm"
                    else reply.content
                )
        try:
            joined = joined_replies(voiced)
        except (wave.Error, EOFError, ValueError) as error:
            raise NonRetryableSpeechError(
                f"the server answered, but not as WAV or MP3: {error}"
            ) from error
        return joined

    async def _voice(
        self,
        client: httpx.AsyncClient,
        index: int,
        total: int,
        turn: SpokenTurn,
        response_format: str,
    ) -> httpx.Response:
        # A request in flight cannot be stopped; a turn not yet sent can.
        cancellation.raise_if_cancelled()
        logger.info(
            "speech: turn %s/%s voice=%s %s chars as %s",
            index,
            total,
            turn.voice,
            len(turn.text),
            response_format,
        )
        try:
            body = {
                "model": self._model,
                "input": turn.text,
                "response_format": response_format,
            }
            # No voice leaves it to the server's default; only a test sends none.
            if turn.voice:
                body["voice"] = turn.voice
            return await client.post(f"{self._base_url}/audio/speech", json=body)
        except httpx.HTTPError as error:
            raise NonRetryableSpeechError(
                f"the server could not voice turn {index} of {total}: {error}"
            ) from error


def _line_as_wav(reply: httpx.Response, index: int, total: int) -> bytes:
    wav = wav_from_pcm_reply(reply)
    if wav is None:
        raise NonRetryableSpeechError(
            f"the server could not voice turn {index} of {total}: "
            "its audio did not state a sample rate"
        )
    return wav


def _server_message(reply: httpx.Response) -> str:
    """OpenAI's shape, {"error": {"message": ...}}, which most servers copy."""
    try:
        return str(reply.json()["error"]["message"])
    except (ValueError, KeyError, TypeError):
        return f"HTTP {reply.status_code}"
