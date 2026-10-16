"""Speech cut into the windows the recogniser is sent: at most 28 s each, cut at
pauses, silence between them never sent, and each window at its own place in
the recording so the transcript keeps its times."""

import pytest

from modules.llm.transcription.voice_activity.speech_spans import SpeechSpan
from worker.ingestion.audio.speech_regions import padded
from worker.ingestion.audio.windows import Window, plan_windows

pytestmark = pytest.mark.unit

FRAME = 0.032


def steady(seconds: float) -> list[float]:
    """One loudness for every frame: nowhere quieter than anywhere else."""
    return [1.0] * int(seconds / FRAME + 1)


def test_speech_that_fits_is_one_window() -> None:
    """A short memo goes in one request, its pause included."""
    regions = [SpeechSpan(1.0, 5.0), SpeechSpan(6.0, 10.0)]

    assert plan_windows(regions, steady(11), FRAME) == [Window(1.0, 10.0)]


def test_silence_between_windows_is_never_sent() -> None:
    """Two remarks a minute and a half apart: the quiet between them stays home."""
    regions = [SpeechSpan(2.0, 6.0), SpeechSpan(100.0, 104.0)]

    assert plan_windows(regions, steady(105), FRAME) == [
        Window(2.0, 6.0),
        Window(100.0, 104.0),
    ]


def test_a_window_ends_at_the_longest_pause_past_20_seconds() -> None:
    """Of the places it could end between 20 and 28 s, the clearest break."""
    regions = [
        SpeechSpan(0.0, 10.0),
        SpeechSpan(10.4, 20.5),
        # 1 s pause: the cut.
        SpeechSpan(21.5, 24.0),
        SpeechSpan(24.3, 27.0),
        SpeechSpan(27.5, 35.0),
    ]

    assert plan_windows(regions, steady(36), FRAME) == [
        Window(0.0, 20.5),
        Window(21.5, 35.0),
    ]


def test_no_window_is_longer_than_28_seconds() -> None:
    """28 s bounds a request's memory, whatever the speaker does."""
    regions = [SpeechSpan(n * 4.0, n * 4.0 + 3.0) for n in range(30)]

    windows = plan_windows(regions, steady(121), FRAME)

    assert all(w.end_s - w.start_s <= 28.0 for w in windows)
    assert windows[0].start_s == 0.0
    assert windows[-1].end_s == 119.0
    # Each window starts where speech does: nothing from a pause before it.
    starts = {r.start_s for r in regions}
    assert all(w.start_s in starts for w in windows)


def test_a_long_run_without_a_pause_is_cut_where_it_is_quietest() -> None:
    """A lecturer who never stops is cut in the quietest 100 ms between 20 and
    28 s, and the next window starts right there."""
    levels = steady(51)
    quiet = int(23.0 / FRAME)
    levels[quiet : quiet + 3] = [0.0, 0.0, 0.0]

    first, *rest = plan_windows([SpeechSpan(0.0, 50.0)], levels, FRAME)

    assert first.start_s == 0.0
    assert first.end_s == pytest.approx((quiet + 1.5) * FRAME)
    assert rest[0].start_s == first.end_s
    assert rest[-1].end_s == 50.0
    assert all(w.end_s - w.start_s <= 28.0 for w in rest)


def test_speech_is_padded_by_200_ms_within_the_recording() -> None:
    """The first and last syllables are not clipped, nor run off either end."""
    assert padded([SpeechSpan(0.1, 1.0), SpeechSpan(5.0, 9.95)], 10.0) == [
        SpeechSpan(0.0, pytest.approx(1.2)),
        SpeechSpan(pytest.approx(4.8), 10.0),
    ]


def test_spans_under_300_ms_apart_once_padded_are_one() -> None:
    """A breath does not split a sentence into two regions."""
    joined = padded([SpeechSpan(1.0, 2.0), SpeechSpan(2.6, 3.0)], 10.0)
    apart = padded([SpeechSpan(1.0, 2.0), SpeechSpan(2.8, 3.0)], 10.0)

    assert joined == [SpeechSpan(pytest.approx(0.8), pytest.approx(3.2))]
    assert len(apart) == 2
