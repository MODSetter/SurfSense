import pytest
from youtube_transcript_api import Transcript

from modules.documents.web_sources.youtube_reading.transcript_tracks import (
    chosen_track,
)

pytestmark = pytest.mark.unit


def track(code: str, generated: bool = False) -> Transcript:
    """A caption track as the video's track list offers it."""
    return Transcript(
        None, "dQw4w9WgXcQ", f"https://t/{code}", code, code, generated, []
    )


def test_a_persons_track_in_the_spoken_language_comes_first() -> None:
    """YouTube's own track says which language is spoken; English is not assumed."""
    chosen = chosen_track([track("en"), track("fr", generated=True), track("fr-FR")])

    assert chosen is not None
    assert chosen.language_code == "fr-FR"


def test_youtubes_own_track_stands_in_for_a_persons_in_that_language() -> None:
    """A subtitle in another language is a translation, not what was said."""
    chosen = chosen_track([track("en"), track("de", generated=True)])

    assert chosen is not None
    assert chosen.language_code == "de"


def test_with_no_track_of_youtubes_own_the_first_persons_track_is_kept() -> None:
    """Nothing says which language is spoken."""
    chosen = chosen_track([track("es"), track("en")])

    assert chosen is not None
    assert chosen.language_code == "es"


def test_a_video_without_tracks_has_none() -> None:
    """No captions at all."""
    assert chosen_track([]) is None
