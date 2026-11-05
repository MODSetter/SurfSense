"""A line's raw PCM as a WAV, so it joins with a pause like any other WAV."""

import io
import wave
from email.message import Message

import httpx

from modules.llm.providers.openai_compatible.joined_replies import joins_as_it_is

__all__ = ["line_from_pcm_request"]

# OpenRouter's API states 16-bit little-endian PCM; the header states no width.
_SAMPLE_WIDTH = 2


def line_from_pcm_request(reply: httpx.Response) -> bytes | None:
    """What a `pcm` request's answer gives the episode, or None when it gives
    nothing it can use. A server may answer in another format, and that line is
    billed, so asking again would pay for it twice."""
    wav = _wav_from_pcm_reply(reply)
    if wav is not None:
        return wav
    return reply.content if joins_as_it_is(reply.content) else None


def _wav_from_pcm_reply(reply: httpx.Response) -> bytes | None:
    """None when the header does not state a rate: the bytes carry none, and a
    guessed one would play the voice at the wrong pitch."""
    header = Message()
    header["content-type"] = reply.headers.get("content-type", "")
    if header.get_content_type() != "audio/pcm":
        return None
    try:
        rate = int(header.get_param("rate") or 0)
        # Mono when unstated, as RFC 2586 has it for raw 16-bit audio.
        channels = int(header.get_param("channels") or 1)
    except (TypeError, ValueError):
        return None
    if rate <= 0 or channels <= 0:
        return None
    out = io.BytesIO()
    with wave.open(out, "wb") as line:
        line.setnchannels(channels)
        line.setsampwidth(_SAMPLE_WIDTH)
        line.setframerate(rate)
        line.writeframes(reply.content)
    return out.getvalue()
