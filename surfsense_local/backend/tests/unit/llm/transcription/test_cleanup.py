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


def test_a_comma_or_full_stop_written_apart_joins_its_word() -> None:
    """Canary writes German with a space before them."""
    assert cleaned("Der Bericht zeigt , dass er steigt .", "de", 3.0) == (
        "Der Bericht zeigt, dass er steigt."
    )


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("Il a dit : pourquoi pas ?", id="French spacing"),
        pytest.param("It costs .5 dollars", id="a decimal"),
        pytest.param("Wait ... what", id="an ellipsis"),
    ],
)
def test_other_spacing_around_punctuation_is_kept(text: str) -> None:
    """Only a lone comma or full stop moves."""
    assert cleaned(text, "fr", 3.0) == text


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


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("收入是100000元", id="a number"),
        pytest.param("他说Hmmmm好吧", id="a Latin word"),
    ],
)
def test_a_number_or_latin_word_in_chinese_is_one_unit(text: str) -> None:
    """Its zeros or letters are not a run of characters said four times."""
    assert cleaned(text, "zh", 5.0) == text


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
