"""Speech packed into the windows the recogniser is sent. 28 s bounds a request's
memory: Nemotron's offline mode runs one encoder graph over the whole request,
and over 28 s windows it peaked at 1,370 MiB. Windows aim at 24 s and end at
the longest pause; silence between them is never sent, and each keeps its
place in the recording, so timestamps survive."""

from collections.abc import Sequence
from dataclasses import dataclass

from modules.llm.transcription.voice_activity.speech_spans import SpeechSpan

__all__ = ["MAX_WINDOW_S", "Window", "plan_windows"]

MAX_WINDOW_S = 28.0
_AIM_S = 24.0
# A window may end at a pause once it holds this much.
_SHORTEST_CUT_S = 20.0
_QUIET_S = 0.1


@dataclass(frozen=True)
class Window:
    start_s: float
    end_s: float


def plan_windows(
    regions: Sequence[SpeechSpan], levels: Sequence[float], frame_s: float
) -> list[Window]:
    """`regions` in order and apart; `levels` each frame's loudness, read when
    one run of speech outlasts a window and must be cut inside."""
    queue = list(regions)
    windows: list[Window] = []
    at = 0
    while at < len(queue):
        start = queue[at].start_s
        if queue[at].end_s - start > MAX_WINDOW_S:
            cut = _quietest(levels, frame_s, start + _SHORTEST_CUT_S, start)
            windows.append(Window(start, cut))
            queue[at] = SpeechSpan(cut, queue[at].end_s)
            continue
        last = at
        while last + 1 < len(queue) and queue[last + 1].end_s - start <= MAX_WINDOW_S:
            last += 1
        if last + 1 == len(queue):
            windows.append(Window(start, queue[last].end_s))
            break
        end = _end_at_a_pause(queue, at, last, start)
        windows.append(Window(start, queue[end].end_s))
        at = end + 1
    return windows


def _end_at_a_pause(
    queue: Sequence[SpeechSpan], first: int, last: int, start: float
) -> int:
    """The region to end after: the longest pause once 20 s are held, the one
    nearest 24 s among equals; else every region that fits."""
    long_enough = [
        n for n in range(first, last + 1) if queue[n].end_s - start >= _SHORTEST_CUT_S
    ]
    if not long_enough:
        return last
    return max(
        long_enough,
        key=lambda n: (
            queue[n + 1].start_s - queue[n].end_s,
            -abs(queue[n].end_s - start - _AIM_S),
        ),
    )


def _quietest(
    levels: Sequence[float], frame_s: float, earliest: float, start: float
) -> float:
    """The middle of the quietest 100 ms between `earliest` and the window's
    end, in time; the aim when the levels do not reach that far."""
    span = max(1, round(_QUIET_S / frame_s))
    first = int(earliest / frame_s) + 1
    last = int((start + MAX_WINDOW_S) / frame_s) - span
    if last >= len(levels) - span:
        last = len(levels) - span
    if last < first:
        return start + _AIM_S
    quietest = min(range(first, last + 1), key=lambda f: sum(levels[f : f + span]))
    return (quietest + span / 2) * frame_s
