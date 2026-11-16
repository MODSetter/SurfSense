"""The one dictation that may be open: from the mic press until its last phrase,
20 s without a phrase or keepalive, or 6 minutes."""

import pytest

from modules.llm.transcription.sessions import DictationEndedError, DictationSessions

pytestmark = pytest.mark.unit


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock() -> Clock:
    """Time that moves only when a test moves it."""
    return Clock()


@pytest.fixture
def sessions(clock: Clock) -> DictationSessions:
    """The dictations of one API process."""
    return DictationSessions(clock=clock)


def test_an_open_dictation_takes_phrases(sessions: DictationSessions) -> None:
    """From the mic press on."""
    dictation = sessions.open()

    sessions.touch(dictation)

    assert sessions.any_open()


def test_opening_another_ends_the_first(sessions: DictationSessions) -> None:
    """Its later phrases are told it ended."""
    first = sessions.open()
    second = sessions.open()

    with pytest.raises(DictationEndedError):
        sessions.touch(first)
    sessions.touch(second)


def test_twenty_quiet_seconds_end_it(sessions: DictationSessions, clock: Clock) -> None:
    """The composer died or the network dropped: recordings go on."""
    dictation = sessions.open()
    clock.now += 20

    assert not sessions.any_open()
    with pytest.raises(DictationEndedError):
        sessions.touch(dictation)


def test_each_phrase_or_keepalive_keeps_it_open(
    sessions: DictationSessions, clock: Clock
) -> None:
    """A speaker pausing to think keeps the mic."""
    dictation = sessions.open()
    for _ in range(5):
        clock.now += 15
        sessions.touch(dictation)

    assert sessions.any_open()


def test_six_minutes_end_it_however_busy(
    sessions: DictationSessions, clock: Clock
) -> None:
    """Recording stops at five; the last phrases land within the sixth."""
    dictation = sessions.open()
    for _ in range(35):
        clock.now += 10
        sessions.touch(dictation)
    clock.now += 10

    with pytest.raises(DictationEndedError):
        sessions.touch(dictation)
    assert not sessions.any_open()


def test_closing_ends_it_and_closing_again_is_harmless(
    sessions: DictationSessions,
) -> None:
    """Stop, cancel and unmount may all close it."""
    dictation = sessions.open()

    sessions.close(dictation)
    sessions.close(dictation)
    sessions.close("never-opened")

    assert not sessions.any_open()
    with pytest.raises(DictationEndedError):
        sessions.touch(dictation)


def test_closing_an_ended_one_leaves_the_open_one(
    sessions: DictationSessions,
) -> None:
    """A late close from a replaced dictation changes nothing."""
    first = sessions.open()
    second = sessions.open()

    sessions.close(first)

    sessions.touch(second)
