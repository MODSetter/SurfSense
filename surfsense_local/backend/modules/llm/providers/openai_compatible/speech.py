"""Podcast voices from a server's /audio/speech, one request per turn."""

import logging
import wave

import httpx

from modules.llm.connections.key_headers import key_headers
from modules.llm.providers.openai_compatible.joined_replies import joined_replies
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
            # WAV first, because only WAV takes a pause between speakers.
            # OpenRouter takes only mp3 or pcm, and pcm states no sample rate.
            chosen = "wav"
            for index, turn in enumerate(turns, start=1):
                reply = await self._voice(client, index, len(turns), turn, chosen)
                if reply.is_error and index == 1:
                    # Asked once, on the first line: a refusal after it is
                    # that line's own, not the format's.
                    retry = await self._voice(client, index, len(turns), turn, "mp3")
                    if not retry.is_error:
                        chosen, reply = "mp3", retry
                if reply.is_error:
                    raise NonRetryableSpeechError(
                        f"the server could not voice turn {index} of {len(turns)}: "
                        f"{_server_message(reply)}"
                    )
                voiced.append(reply.content)
        try:
            return joined_replies(voiced)
        except (wave.Error, EOFError, ValueError) as error:
            raise NonRetryableSpeechError(
                f"the server answered, but not as WAV or MP3: {error}"
            ) from error

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


def _server_message(reply: httpx.Response) -> str:
    """OpenAI's shape, {"error": {"message": ...}}, which most servers copy."""
    try:
        return str(reply.json()["error"]["message"])
    except (ValueError, KeyError, TypeError):
        return f"HTTP {reply.status_code}"
