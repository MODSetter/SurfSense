"""The two API routes a recording's job calls: whether speech recognition can
run, and one window at a time. Workers reach the transcription server only
through the API, whose gate orders every request (ADR 0056)."""

from dataclasses import dataclass

import httpx

__all__ = [
    "NeedsSpeechModelError",
    "SpeechStatus",
    "TranscriptionApi",
    "UnavailableError",
    "WaitingError",
    "WindowText",
]

# The route waits up to 30 s for its turn, then gives the server
# max(120 s, 20 x the audio), as the API's client does.
_TURN_WAIT_S = 30.0
_SLACK_S = 30.0
# The status route's word for "let the model detect it".
_DETECT = "auto"


@dataclass(frozen=True)
class SpeechStatus:
    ready: bool
    # `needs_speech_model`, `transcription_unavailable`, or None when ready.
    reason: str | None
    model: str | None
    # `auto`, or the code the user set.
    language_intent: str
    # The codes the model is listed for.
    languages: tuple[str, ...]

    @property
    def pinned_language(self) -> str | None:
        """The language the user set, or None when the model detects it."""
        return None if self.language_intent == _DETECT else self.language_intent


@dataclass(frozen=True)
class WindowText:
    text: str
    language: str | None
    model_id: str


class NeedsSpeechModelError(Exception):
    """None is chosen, or it was deleted since the job began."""


class UnavailableError(Exception):
    """The server or the API is restarting or stopped; asked again later."""


class WaitingError(Exception):
    """Not this window's turn yet: someone dictates, the text runtime is held,
    memory is short, or another window is in flight."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


class TranscriptionApi:
    def __init__(
        self, base_url: str, *, transport: httpx.BaseTransport | None = None
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._transport = transport

    def status(self) -> SpeechStatus:
        reply = self._request("GET", "/llm/transcription/status", timeout=10.0)
        reply.raise_for_status()
        body = reply.json()
        return SpeechStatus(
            ready=body["ready"],
            reason=body["reason"],
            model=body["model"],
            language_intent=body["language_intent"],
            languages=tuple(body["languages"]),
        )

    def transcribe(self, wav: bytes, *, seconds: float, last: bool) -> WindowText:
        """`last`: no other recording waits, so the model can go once done."""
        reply = self._request(
            "POST",
            "/internal/transcription/windows",
            timeout=_TURN_WAIT_S + max(120.0, 20 * seconds) + _SLACK_S,
            files={"audio": ("window.wav", wav, "audio/wav")},
            data={"last": "true" if last else "false"},
        )
        if reply.status_code in (409, 503):
            _raise_refusal(reply)
        reply.raise_for_status()
        body = reply.json()
        return WindowText(body["text"], body["language"], body["model_id"])

    def _request(
        self, method: str, path: str, *, timeout: float, **content: object
    ) -> httpx.Response:
        try:
            with httpx.Client(
                timeout=httpx.Timeout(timeout, connect=5.0), transport=self._transport
            ) as client:
                return client.request(method, f"{self._base_url}{path}", **content)
        except httpx.TransportError as error:
            raise UnavailableError(str(error)) from error


def _raise_refusal(reply: httpx.Response) -> None:
    try:
        detail = reply.json()["detail"]
        code = detail["code"]
    except (ValueError, KeyError, TypeError):
        reply.raise_for_status()
        return
    if code == "needs_speech_model":
        raise NeedsSpeechModelError(detail.get("message", code))
    if code == "waiting":
        raise WaitingError(detail.get("reason", "busy"), detail.get("message", code))
    if code == "transcription_unavailable":
        raise UnavailableError(detail.get("message", code))
    reply.raise_for_status()
