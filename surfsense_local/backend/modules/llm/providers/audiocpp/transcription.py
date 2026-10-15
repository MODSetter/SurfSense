"""Speech written down by the transcription server, audio.cpp run a second
time: one clip per request, sent from memory, never through a file."""

import asyncio
import io
import logging
import wave

import httpx

from modules.llm.activity import model_activity, model_key
from modules.llm.providers.audiocpp import PROVIDER
from modules.llm.providers.protocols import TranscriptionUnavailableError

__all__ = ["AudioCppTranscriber"]

logger = logging.getLogger(__name__)

# Handy's rule: a hung server fails one request, and a slow CPU still finishes.
_MIN_DEADLINE_SECONDS = 120.0
_DEADLINE_PER_AUDIO_SECOND = 20.0
# Long enough for a restart after a crash or a new config to take the port.
RETRY_AFTER_SECONDS = 2.0
_QUICK = httpx.Timeout(10.0, connect=5.0)
# A server restarting refuses the connection, drops it, or answers 503.
_RESTARTING = (httpx.NetworkError, httpx.RemoteProtocolError)


class AudioCppTranscriber:
    def __init__(
        self,
        base_url: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        retry_after: float | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._transport = transport
        self._retry_after = RETRY_AFTER_SECONDS if retry_after is None else retry_after

    async def transcribe(self, model: str, wav: bytes, language: str | None) -> str:
        fields = {"model": model}
        if language is not None:
            fields["language"] = language
        deadline = max(
            _MIN_DEADLINE_SECONDS, _DEADLINE_PER_AUDIO_SECOND * _seconds(wav)
        )
        key = model_key(PROVIDER, model)
        # Held for the request, so a delete in the middle is refused.
        await model_activity.acquire_use(key)
        try:
            async with self._client(httpx.Timeout(deadline, connect=5.0)) as client:
                reply = await self._post_once_more_if_restarting(client, wav, fields)
        except httpx.HTTPError as error:
            # Past its deadline, say: it had its time, so it is not asked again.
            raise TranscriptionUnavailableError(
                f"the speech recognition server did not answer: {error!r}"
            ) from error
        finally:
            await model_activity.release_use(key)
        if reply.is_error:
            raise TranscriptionUnavailableError(_server_message(reply))
        try:
            return str(reply.json().get("text", ""))
        except (ValueError, AttributeError) as error:
            raise TranscriptionUnavailableError(
                f"the speech recognition server answered without text: {error!r}"
            ) from error

    async def is_loaded(self, model: str) -> bool:
        try:
            async with self._client(_QUICK) as client:
                reply = await client.get("/v1/models")
            reply.raise_for_status()
            listed = {entry["id"]: entry for entry in reply.json()["data"]}
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
            raise TranscriptionUnavailableError(
                f"the speech recognition server did not answer: {error}"
            ) from error
        if model not in listed:
            # Its config names another model: Electron has yet to restart it.
            raise TranscriptionUnavailableError(f"the server does not run {model}")
        return bool(listed[model].get("loaded"))

    async def unload(self, model: str) -> None:
        try:
            async with self._client(_QUICK) as client:
                reply = await client.post(
                    "/v1/tasks/unload_models", json={"model_ids": [model]}
                )
            reply.raise_for_status()
        except httpx.HTTPError:
            logger.warning("transcription: could not unload; the idle timer will")

    def _client(self, timeout: httpx.Timeout) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self._base_url, timeout=timeout, transport=self._transport
        )

    async def _post_once_more_if_restarting(
        self, client: httpx.AsyncClient, wav: bytes, fields: dict[str, str]
    ) -> httpx.Response:
        try:
            reply = await _post(client, wav, fields)
            if reply.status_code != 503:
                return reply
        except _RESTARTING:
            pass
        await asyncio.sleep(self._retry_after)
        try:
            return await _post(client, wav, fields)
        except _RESTARTING as error:
            raise TranscriptionUnavailableError(
                f"the speech recognition server did not answer: {error}"
            ) from error


async def _post(
    client: httpx.AsyncClient, wav: bytes, fields: dict[str, str]
) -> httpx.Response:
    return await client.post(
        "/v1/audio/transcriptions/details",
        data=fields,
        files={"file": ("audio.wav", wav, "audio/wav")},
    )


def _seconds(wav: bytes) -> float:
    with wave.open(io.BytesIO(wav)) as clip:
        return clip.getnframes() / clip.getframerate()


def _server_message(reply: httpx.Response) -> str:
    """audio.cpp answers a failure with {"error": {"message": ...}}."""
    try:
        return str(reply.json()["error"]["message"])
    except (ValueError, KeyError, TypeError):
        return f"HTTP {reply.status_code}"
