"""Visual media: a drawn image and a painted infographic."""

import pytest

from modules.llm.profile import Tier
from modules.llm.providers.protocols import GeneratedImage
from modules.llm.resolution import ResolvedGeneration, ResolvedImageGeneration
from worker.studio.media.visual.image import pipeline as image
from worker.studio.media.visual.image import schema as image_schema
from worker.studio.media.visual.infographic import pipeline as infographic
from worker.studio.media.visual.infographic import schema as infographic_schema
from worker.studio.shared.artifact import Source

pytestmark = pytest.mark.unit

PNG = b"\x89PNG\r\n\x1a\nfake image bytes"


def _writer() -> ResolvedGeneration:
    """The chat model that briefs the painter; its call is stubbed, its tier is not."""
    selection = type("Selection", (), {"name": "qwen3:8b", "tier": Tier.CAPABLE})()
    return ResolvedGeneration(selection, None)


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

    def writer(_model: object, system: str, _sources: object, **_kw: object) -> str:
        asked.append(system)
        return '{"title": "Saturn at Dusk", "prompt": "Saturn low over a cold sea"}'

    monkeypatch.setattr("worker.studio.shared.generate.run_model", writer)
    painted: list[str] = []

    built = image.render(
        _painter(painted),
        _writer(),
        [Source(1, "Saturn", "rings, 1610")],
        "make it bold",
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
        "worker.studio.shared.generate.run_model",
        lambda *_a, **_k: '{"prompt": "rings"}',
    )
    sources = [Source(1, "Saturn facts", "rings"), Source(2, "Titan", "methane")]

    built = image.render(_painter([]), _writer(), sources, None)

    assert built.title == "Saturn facts and 1 more"
    assert built.primary_filename == "saturn-facts-and-1-more.png"


def test_an_image_needs_a_prompt_from_the_writer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No prompt is a readable failure, not a blank painting."""
    monkeypatch.setattr(
        "worker.studio.shared.generate.run_model", lambda *_a, **_k: "{}"
    )
    with pytest.raises(ValueError, match="prompt"):
        image.render(_painter([]), _writer(), [Source(1, "Saturn", "rings")], None)


def _asked_schemas(monkeypatch: pytest.MonkeyPatch, reply: str) -> list[dict | None]:
    """Each schema the writer was sent, answering every call with `reply`."""
    sent: list[dict | None] = []

    def writer(*_a: object, json_schema: dict | None = None, **_kw: object) -> str:
        sent.append(json_schema)
        return reply

    monkeypatch.setattr("worker.studio.shared.generate.run_model", writer)
    return sent


def test_an_image_asks_the_writer_for_its_schema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A brief that drifts off its shape paints nothing, so the grammar holds it."""
    sent = _asked_schemas(monkeypatch, '{"title": "Saturn", "prompt": "rings"}')

    image.render(_painter([]), _writer(), [Source(1, "Saturn", "rings")], None)

    assert sent == [image_schema.REPLY]


def test_the_image_schema_asks_for_what_the_builder_keeps() -> None:
    """No prompt fails the job and every tier asks for a title, so both are required."""
    assert set(image_schema.REPLY["required"]) == {"title", "prompt"}


def test_infographic_paints_the_brief_the_chat_model_wrote(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two steps: the chat model distils the facts, the image model draws them."""
    monkeypatch.setattr(
        "worker.studio.shared.generate.run_model",
        lambda *_a, **_k: (
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
    built = infographic.render(painter, _writer(), sources, None)

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


def test_an_infographic_asks_the_writer_for_its_schema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The brief is the picture's only facts; a broken one loses the whole job."""
    sent = _asked_schemas(
        monkeypatch,
        '{"title": "Saturn", "summary": "Rings", "sections": '
        '[{"label": "Count", "value": "7", "detail": "Main rings"}]}',
    )

    infographic.render(_painter([]), _writer(), [Source(1, "Saturn", "rings")], None)

    assert sent == [infographic_schema.REPLY]


def test_the_infographic_schema_asks_for_what_the_builder_keeps() -> None:
    """Every field the prompts ask for, and no more sections than are drawn."""
    reply = infographic_schema.REPLY
    sections = reply["properties"]["sections"]

    assert set(reply["required"]) == {"title", "summary", "sections"}
    assert set(sections["items"]["required"]) == {"label", "value", "detail"}
    assert sections["minItems"] == 1
    assert sections["maxItems"] == infographic.SECTIONS
