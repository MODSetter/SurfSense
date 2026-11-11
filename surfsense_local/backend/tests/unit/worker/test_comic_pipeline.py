"""A Studio comic: the chat model plans it, the image model draws its pages, the binder makes the PDF."""

import io
import json

import pytest
from PIL import Image
from pypdf import PdfReader

from modules.artifacts.comic.options import validate_options
from modules.llm.pictures_in.model import PictureModel
from modules.llm.profile import Tier
from modules.llm.providers.protocols import GeneratedImage
from modules.llm.resolution import ResolvedGeneration, ResolvedImageGeneration
from worker.studio.media.visual.comic import pipeline as comic
from worker.studio.media.visual.drawn.pipeline import DRAWN_FROM_WORDS
from worker.studio.shared.artifact import Source

pytestmark = pytest.mark.unit


def _png(colour: str) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (40, 60), colour).save(out, "PNG")
    return out.getvalue()


PLAN = {
    "title": "The Lighthouse Cat",
    "style": "Bold ink lines, flat colours.",
    "characters": "MILO, a small orange tabby cat with a red scarf.",
    "pages": [
        {
            "panels": [
                {"where": "top", "shows": "A storm hits the lighthouse.", "lines": []},
                {
                    "where": "bottom",
                    "shows": "MILO looks at the dead lamp.",
                    "lines": ["MILO: The light is out!"],
                },
            ]
        },
        {
            "panels": [
                {
                    "where": "whole page",
                    "shows": "MILO finds a bulb.",
                    "lines": ["MILO: Got it!"],
                }
            ]
        },
        {"panels": [{"where": "whole page", "shows": "The lamp shines.", "lines": []}]},
    ],
}


class Artist:
    """The image model, and the model that takes page 1 as reference."""

    def __init__(self) -> None:
        self.drawn: list[str] = []
        self.with_reference: list[tuple[str, bytes]] = []
        self.shapes: list[str | None] = []

    async def generate(
        self, _model: str, prompt: str, *, shape: str | None = None
    ) -> GeneratedImage:
        self.drawn.append(prompt)
        self.shapes.append(shape)
        return GeneratedImage(_png("teal"), "image/png")

    async def edit(
        self,
        _model: str,
        prompt: str,
        images: tuple[GeneratedImage, ...],
        *,
        shape: str | None = None,
    ) -> GeneratedImage:
        (reference,) = images
        self.with_reference.append((prompt, reference.content))
        self.shapes.append(shape)
        return GeneratedImage(_png("navy"), "image/png")


def _writer() -> ResolvedGeneration:
    selection = type("Selection", (), {"name": "qwen3:8b", "tier": Tier.CAPABLE})()
    return ResolvedGeneration(selection, None)


def _painter(
    artist: Artist, provider: str = "openai_compatible"
) -> ResolvedImageGeneration:
    selection = type("Selection", (), {"name": "flux", "provider": provider})()
    return ResolvedImageGeneration(selection, artist)


def _keeper(artist: Artist) -> PictureModel:
    selection = type(
        "Selection", (), {"name": "flux", "provider": "openai_compatible"}
    )()
    return PictureModel("image_model", selection, artist)


@pytest.fixture
def asked(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """The chat model answers with PLAN; what it was asked is recorded."""
    seen: list[str] = []

    def writer(_model: object, system: str, _sources: object, **_asked: object) -> str:
        seen.append(system)
        return json.dumps(PLAN)

    monkeypatch.setattr("worker.studio.shared.generate.run_model", writer)
    return seen


def _text(pdf: bytes) -> str:
    return "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(pdf)).pages)


def test_page_one_is_drawn_alone_and_every_later_page_keeps_its_characters(
    asked: list[str],
) -> None:
    """Page 1 sets the cast; every later page is drawn from it, lettered in its bubbles."""
    artist = Artist()

    built = comic.render(
        _painter(artist),
        _writer(),
        [Source(1, "Lighthouse", "A cat keeps the light.")],
        "make it funny",
        {"kind": "western", "pages": 3},
        keeper=_keeper(artist),
    )

    assert "make it funny" in asked[0]
    assert "Western comic" in asked[0]
    (first,) = artist.drawn
    assert "Page 1 of 3" in first
    assert "MILO, a small orange tabby cat" in first
    assert 'MILO says: "The light is out!"' in first
    assert [prompt.split("Page ")[1][:6] for prompt, _ in artist.with_reference] == [
        "2 of 3",
        "3 of 3",
    ]
    assert all(reference == _png("teal") for _, reference in artist.with_reference)
    assert all(
        "Keep the characters looking exactly as in the reference" in p
        for p, _ in artist.with_reference
    )
    assert set(artist.shapes) == {"portrait"}
    assert built.title == "The Lighthouse Cat"
    assert built.primary_mime == "application/pdf"
    assert built.primary_filename == "the-lighthouse-cat.pdf"
    assert len(PdfReader(io.BytesIO(built.primary)).pages) == 3
    # Drawn in the bubbles, so not set again under the page.
    assert "The light is out!" not in _text(built.primary)
    assert "The light is out!" in built.markdown


def test_a_local_model_draws_no_words_and_every_line_goes_in_the_strip(
    asked: list[str],
) -> None:
    """Its lettering is not measured, and nobody looks at the page to check it."""
    artist = Artist()

    built = comic.render(
        _painter(artist, provider="sdcpp"),
        _writer(),
        [Source(1, "Lighthouse", "A cat keeps the light.")],
        None,
        {"kind": "western", "pages": 3},
        keeper=_keeper(artist),
    )

    prompts = artist.drawn + [prompt for prompt, _ in artist.with_reference]
    assert all("no text, no lettering, no speech bubbles" in p for p in prompts)
    assert not any("The light is out!" in p for p in prompts)
    assert "MILO: The light is out!" in _text(built.primary)


def test_a_manga_reads_right_to_left_in_its_pages_and_its_book(
    asked: list[str],
) -> None:
    """Each page's prompt and the bound book both read right to left."""
    artist = Artist()

    built = comic.render(
        _painter(artist),
        _writer(),
        [Source(1, "Lighthouse", "A cat keeps the light.")],
        None,
        {"kind": "manga", "pages": 3},
        keeper=_keeper(artist),
    )

    assert "read right to left" in artist.drawn[0]
    root = PdfReader(io.BytesIO(built.primary)).trailer["/Root"]
    assert root["/ViewerPreferences"]["/Direction"] == "/R2L"


def test_with_no_model_that_takes_pictures_every_page_is_drawn_from_the_words(
    asked: list[str],
) -> None:
    """Nothing is refused; the comic records that its cast may drift."""
    artist = Artist()

    built = comic.render(
        _painter(artist),
        _writer(),
        [Source(1, "Lighthouse", "A cat keeps the light.")],
        None,
        {"kind": "western", "pages": 3},
        keeper=None,
    )

    assert len(artist.drawn) == 3
    assert artist.with_reference == []
    assert built.metadata is not None and built.metadata[DRAWN_FROM_WORDS] is True


def test_a_plan_longer_than_asked_is_cut_to_the_page_count(asked: list[str]) -> None:
    """Each page is billed or takes minutes: the count the user chose is the most drawn."""
    artist = Artist()

    built = comic.render(
        _painter(artist),
        _writer(),
        [Source(1, "Lighthouse", "A cat keeps the light.")],
        None,
        {"kind": "western", "pages": 2},
        keeper=_keeper(artist),
    )

    assert len(artist.drawn) + len(artist.with_reference) == 2
    assert len(PdfReader(io.BytesIO(built.primary)).pages) == 2


REFUSAL = (
    "I can't turn this document into a comic.\n\n"
    "It glorifies real violence, and a dramatised version would spread it."
)


def _replying(monkeypatch: pytest.MonkeyPatch, *replies: str) -> list[dict]:
    """The chat model answers `replies` in turn; each call's keywords are recorded."""
    calls: list[dict] = []

    def writer(_model: object, _system: str, _sources: object, **asked: object) -> str:
        calls.append(asked)
        return replies[len(calls) - 1]

    monkeypatch.setattr("worker.studio.shared.generate.run_model", writer)
    return calls


def _render_three(artist: Artist) -> object:
    return comic.render(
        _painter(artist),
        _writer(),
        [Source(1, "Lighthouse", "A cat keeps the light.")],
        None,
        {"kind": "western", "pages": 3},
        keeper=_keeper(artist),
    )


def test_the_plan_is_asked_for_in_its_json_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An endpoint that takes a schema cannot answer outside it."""
    calls = _replying(monkeypatch, json.dumps(PLAN))

    _render_three(Artist())

    schema = calls[0]["json_schema"]
    assert schema["required"] == ["title", "style", "characters", "pages"]


def test_a_plan_that_is_not_json_is_asked_for_once_more(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nothing is drawn yet, so asking again costs one text reply, not pages."""
    calls = _replying(
        monkeypatch, "Here is the plan: title The Lighthouse Cat", json.dumps(PLAN)
    )
    artist = Artist()

    built = _render_three(artist)

    assert calls[1]["repair"].reply == "Here is the plan: title The Lighthouse Cat"
    assert built.title == "The Lighthouse Cat"


def test_a_model_that_declines_twice_fails_with_what_it_said(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A refusal reads as one, not as a JSON parse error, and no page is drawn."""
    _replying(monkeypatch, REFUSAL, REFUSAL)
    artist = Artist()

    with pytest.raises(ValueError) as failed:
        _render_three(artist)

    assert str(failed.value).splitlines()[0] == (
        "The model did not plan the comic. It said: "
        "I can't turn this document into a comic."
    )
    assert artist.drawn == []


def test_a_webtoon_is_one_scroll_of_beats() -> None:
    """A webtoon's count is its beats, up to the same twelve."""
    picked = validate_options(None, {"kind": "webtoon", "pages": 8})  # type: ignore[arg-type]
    assert picked == {"kind": "webtoon", "pages": 8}


def test_options_default_to_a_four_page_western_comic() -> None:
    """What the dialog sends when the user changes nothing."""
    assert validate_options(None, None) == {"kind": "western", "pages": 4}  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "raw, words",
    [
        ({"kind": "opera", "pages": 4}, "kind"),
        ({"kind": "western", "pages": 0}, "pages"),
        ({"kind": "western", "pages": 13}, "pages"),
        ({"kind": "western", "pages": "four"}, "pages"),
    ],
)
def test_options_outside_the_kinds_or_twelve_pages_are_refused(
    raw: dict, words: str
) -> None:
    """Refused at the door, naming the option to fix, before any picture is billed."""
    with pytest.raises(ValueError, match=words):
        validate_options(None, raw)  # type: ignore[arg-type]
