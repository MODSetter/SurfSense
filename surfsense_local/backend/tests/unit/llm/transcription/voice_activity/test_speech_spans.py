"""Where speech is, from Silero's probability for each 32 ms frame: Silero's
own rule, at a 0.5 threshold, with at least 250 ms of speech."""

import pytest

from modules.llm.transcription.voice_activity.speech_spans import SpeechSpan, spans_in

pytestmark = pytest.mark.unit

FRAME = 0.032
LOW, HIGH = 0.05, 0.9


def frames(*runs: tuple[float, int]) -> list[float]:
    """Probabilities, run by run."""
    return [p for p, count in runs for _ in range(count)]


def test_no_frame_over_the_threshold_is_no_speech() -> None:
    """Between 0.35 and 0.5 a frame starts nothing."""
    assert spans_in(frames((LOW, 50), (0.45, 10), (LOW, 50))) == []


def test_a_run_of_speech_is_one_span_from_its_first_frame_to_the_quiet() -> None:
    """It ends where the quiet began, once 100 ms of it passed."""
    span = spans_in(frames((LOW, 10), (HIGH, 20), (LOW, 20)))

    assert span == [SpeechSpan(pytest.approx(10 * FRAME), pytest.approx(30 * FRAME))]


def test_under_250_ms_is_not_speech() -> None:
    """A cough or a keystroke: 7 frames is 224 ms."""
    assert spans_in(frames((LOW, 10), (HIGH, 7), (LOW, 20))) == []


def test_a_pause_under_100_ms_does_not_split_speech() -> None:
    """A breath between words is part of the speech."""
    (span,) = spans_in(frames((LOW, 5), (HIGH, 10), (LOW, 3), (HIGH, 10), (LOW, 20)))

    assert (span.start_s, span.end_s) == (
        pytest.approx(5 * FRAME),
        pytest.approx(28 * FRAME),
    )


def test_a_longer_pause_ends_one_span_and_starts_the_next() -> None:
    """Each span keeps its own times."""
    spans = spans_in(frames((HIGH, 10), (LOW, 10), (HIGH, 10), (LOW, 20)))

    assert [(s.start_s, s.end_s) for s in spans] == [
        (0.0, pytest.approx(10 * FRAME)),
        (pytest.approx(20 * FRAME), pytest.approx(30 * FRAME)),
    ]


def test_speech_that_runs_to_the_end_ends_with_the_audio() -> None:
    """A phrase cut mid-word still counts."""
    (span,) = spans_in(frames((LOW, 4), (HIGH, 12)))

    assert span.end_s == pytest.approx(16 * FRAME)
