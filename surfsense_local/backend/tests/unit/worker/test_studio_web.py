"""Web kind: the model's JSON becomes a self-contained, escaped HTML page."""

from types import SimpleNamespace

import pytest

from modules.llm.profile import Tier
from worker.studio.shared import generate
from worker.studio.web.html import pipeline as html
from worker.studio.web.html import schema as html_schema

pytestmark = pytest.mark.unit


def test_html_escapes_model_text_so_it_cannot_carry_a_script() -> None:
    """The model supplies text only; markup it sends is neutralised, not run."""
    raw = '{"title": "T", "sections": [{"heading": "H", "paragraphs": ["<script>x</script>"]}]}'
    built = html.build(raw, [])

    assert built.primary_mime == "text/html"
    body = built.primary.decode()
    assert "<script>" not in body
    assert "&lt;script&gt;" in body


def test_a_page_asks_the_model_for_its_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    """The page template reads exactly these fields; a reply off them is an empty page."""
    sent: list[dict | None] = []

    def fake_run_model(*_args: object, json_schema: dict | None = None, **_kw: object):
        sent.append(json_schema)
        return '{"title": "T", "sections": []}'

    monkeypatch.setattr(generate, "run_model", fake_run_model)

    html.render(SimpleNamespace(tier=Tier.COMPACT), [], None)

    assert sent == [html_schema.REPLY]


def test_the_page_schema_asks_for_what_the_template_renders() -> None:
    """A section is a heading over its paragraphs, every one plain text."""
    section = html_schema.REPLY["properties"]["sections"]["items"]

    assert set(html_schema.REPLY["required"]) == {"title", "sections"}
    assert set(section["required"]) == {"heading", "paragraphs"}
    assert section["properties"]["paragraphs"]["items"] == {"type": "string"}
