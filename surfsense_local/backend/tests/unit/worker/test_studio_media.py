"""Visual media: a drawn image and a painted infographic."""

import pytest

from modules.llm.providers.protocols import GeneratedImage
from modules.llm.resolution import ResolvedImageGeneration
from worker.studio.media.visual.image import pipeline as image
from worker.studio.media.visual.infographic import pipeline as infographic
from worker.studio.shared.artifact import Source

pytestmark = pytest.mark.unit

PNG = b"\x89PNG\r\n\x1a\nfake image bytes"


def _painter(painted: list[str]) -> ResolvedImageGeneration:
    class FakeImageGenerator:
        async def generate(self, model: str, prompt: str) -> GeneratedImage:
            assert model == "flux"
            painted.append(prompt)
            return GeneratedImage(PNG, "image/png")

    selection = type("Selection", (), {"name": "flux"})()
    return ResolvedImageGeneration(selection, FakeImageGenerator())


def test_image_paints_the_prompt_the_writer_crafted_and_takes_its_title(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two steps: the chat model names the piece and writes the image prompt from
    the sources; the image model paints that, never the raw source text."""
    asked: list[str] = []

    def writer(_model: object, system: str, _sources: object) -> str:
        asked.append(system)
        return '{"title": "Saturn at Dusk", "prompt": "Saturn low over a cold sea"}'

    monkeypatch.setattr("worker.studio.shared.generate.run_model", writer)
    painted: list[str] = []

    built = image.render(
        _painter(painted), None, [Source(1, "Saturn", "rings, 1610")], "make it bold"
    )

    assert "make it bold" in asked[0]
    assert painted == ["Saturn low over a cold sea"]
    assert built.title == "Saturn at Dusk"
    assert built.primary == PNG
    assert built.primary_mime == "image/png"
    assert built.primary_filename == "saturn-at-dusk.png"
    assert "Saturn low over a cold sea" in built.markdown


def test_an_image_the_writer_left_untitled_is_named_after_its_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two images in a list must not both read "Image"."""
    monkeypatch.setattr(
        "worker.studio.shared.generate.run_model", lambda *_: '{"prompt": "rings"}'
    )
    sources = [Source(1, "Saturn facts", "rings"), Source(2, "Titan", "methane")]

    built = image.render(_painter([]), None, sources, None)

    assert built.title == "Saturn facts and 1 more"
    assert built.primary_filename == "saturn-facts-and-1-more.png"


def test_an_image_needs_a_prompt_from_the_writer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No prompt is a readable failure, not a blank painting."""
    monkeypatch.setattr("worker.studio.shared.generate.run_model", lambda *_: "{}")
    with pytest.raises(ValueError, match="prompt"):
        image.render(_painter([]), None, [Source(1, "Saturn", "rings")], None)


def test_infographic_paints_the_brief_the_chat_model_wrote(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two steps: the chat model distils the facts, the image model draws them."""
    monkeypatch.setattr(
        "worker.studio.shared.generate.run_model",
        lambda *_: (
            '{"title":"Saturn","summary":"Rings","sections":'
            '[{"label":"Count","value":"7","detail":"Main rings"}]}'
        ),
    )
    painted: list[str] = []

    class FakeImageGenerator:
        async def generate(self, model: str, prompt: str) -> GeneratedImage:
            painted.append(prompt)
            return GeneratedImage(PNG, "image/png")

    selection = type("Selection", (), {"name": "flux"})()
    painter = ResolvedImageGeneration(selection, FakeImageGenerator())
    sources = [Source(1, "Saturn", "Galileo saw the rings in 1610.")]
    built = infographic.render(painter, None, sources, None)

    # The image prompt carries the brief and a style, not the raw sources.
    assert "Saturn" in painted[0] and "Count: 7" in painted[0]
    assert "1610" not in painted[0]
    assert "sketchnote" in painted[0]
    assert built.primary == PNG
    assert built.primary_mime == "image/png"
    assert built.primary_filename == "saturn.png"
    # The brief is the searchable body, so the picture is findable by its facts.
    assert built.title == "Saturn"
    assert "**7**" in built.markdown
