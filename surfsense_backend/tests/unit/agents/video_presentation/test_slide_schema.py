"""The slide schema tolerates a missing or malformed language.

Narration has a fallback chain; slide generation does not. A model that omits
``language`` or answers with a non-string must still produce a usable deck,
otherwise adding the field would trade a wrong-voice bug for a total failure.
"""

from __future__ import annotations

import pytest

from app.agents.video_presentation.state import PresentationSlides

pytestmark = pytest.mark.unit


def _slide() -> dict:
    return {
        "slide_number": 1,
        "title": "Title",
        "subtitle": "Subtitle",
        "content_in_markdown": "## Heading",
        "speaker_transcripts": ["One sentence."],
        "background_explanation": "Warm and organic",
    }


def test_language_defaults_to_empty_when_the_model_omits_it():
    """Replies in the pre-change shape must keep parsing."""
    presentation = PresentationSlides.model_validate({"slides": [_slide()]})
    assert presentation.language == ""
    assert len(presentation.slides) == 1


@pytest.mark.parametrize("language", [42, None, {"tag": "en"}, ["en"], 1.5])
def test_a_non_string_language_is_coerced_not_rejected(language):
    presentation = PresentationSlides.model_validate(
        {"language": language, "slides": [_slide()]}
    )
    assert presentation.language == ""
    assert len(presentation.slides) == 1


def test_a_declared_language_is_kept_verbatim_on_the_model():
    """Validation of the tag itself belongs to narration, not to the schema."""
    presentation = PresentationSlides.model_validate(
        {"language": "pt-BR", "slides": [_slide()]}
    )
    assert presentation.language == "pt-BR"
