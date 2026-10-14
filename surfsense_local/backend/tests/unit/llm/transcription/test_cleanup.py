"""What a recogniser's text goes through before anyone reads it, the same for
a dictated phrase and a recording's window."""

import pytest

from modules.llm.transcription.cleanup import cleaned

pytestmark = pytest.mark.unit


def test_plain_speech_comes_through_trimmed() -> None:
    """Nothing else changes in ordinary speech."""
    assert cleaned("  The report is due on Friday.  ", "en", 3.0) == (
        "The report is due on Friday."
    )


@pytest.mark.parametrize(
    ("text", "kept"),
    [
        pytest.param(
            "thank you thank you thank you thank you", "thank you", id="two words"
        ),
        pytest.param(
            "so so so so so so we start", "so we start", id="one word, then more"
        ),
        pytest.param(
            "I said a b c d a b c d a b c d a b c d done",
            "I said a b c d done",
            id="four words",
        ),
    ],
)
def test_a_run_repeated_four_times_or_more_is_said_once(text: str, kept: str) -> None:
    """Runaway repetition, the known decoder failure."""
    assert cleaned(text, "en", 10.0) == kept


def test_three_times_is_still_speech() -> None:
    """ "No, no, no" is something people say."""
    assert cleaned("no no no", "en", 2.0) == "no no no"


def test_chinese_repeats_are_counted_in_characters() -> None:
    """No spaces between words, so a run is characters, not words."""
    assert cleaned("好的好的好的好的好的我们开始", "zh", 5.0) == "好的我们开始"


def test_text_faster_than_anyone_speaks_is_dropped() -> None:
    """Over 40 characters a second of audio is a decoder running away."""
    assert cleaned("The model wrote far more than was said here.", "en", 1.0) == ""


def test_text_that_compresses_like_a_loop_is_dropped() -> None:
    """A phrase looping in longer runs than a collapse catches compresses
    past 2.4."""
    looping = "we will meet again tomorrow morning " * 6

    assert cleaned(looping, "en", 30.0) == ""


def test_a_short_text_is_never_judged_by_its_compression() -> None:
    """Under 50 characters the ratio says nothing."""
    assert cleaned("go go go stop", "en", 2.0) == "go go go stop"
