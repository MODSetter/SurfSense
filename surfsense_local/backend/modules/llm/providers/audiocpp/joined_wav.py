"""One WAV from each turn's, with a pause between speakers. WAV out: the
browser plays it and the standard library writes it, with no encoder to ship.
"""

import io
import wave
from collections.abc import Sequence

# Between turns, so the hosts do not run together.
GAP_SECONDS = 0.35


def joined_wav(turns: Sequence[bytes]) -> bytes:
    """The turns in order, which must share one format, as one model's do."""
    frames: list[bytes] = []
    params = None
    for index, content in enumerate(turns):
        with wave.open(io.BytesIO(content)) as turn:
            current = (turn.getnchannels(), turn.getsampwidth(), turn.getframerate())
            if params is None:
                params = current
            elif current != params:
                raise ValueError("the turns came back in different audio formats")
            if index:
                channels, width, rate = params
                frames.append(b"\x00" * round(GAP_SECONDS * rate) * width * channels)
            frames.append(turn.readframes(turn.getnframes()))
    if params is None:
        raise ValueError("nothing was voiced")
    out = io.BytesIO()
    with wave.open(out, "wb") as joined:
        joined.setnchannels(params[0])
        joined.setsampwidth(params[1])
        joined.setframerate(params[2])
        joined.writeframes(b"".join(frames))
    return out.getvalue()
