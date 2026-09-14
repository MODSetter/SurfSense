"""Web kind: the model's JSON becomes a self-contained, escaped HTML page."""

import pytest

from worker.studio.web.html import pipeline as html

pytestmark = pytest.mark.unit


def test_html_escapes_model_text_so_it_cannot_carry_a_script() -> None:
    """The model supplies text only; markup it sends is neutralised, not run."""
    raw = '{"title": "T", "sections": [{"heading": "H", "paragraphs": ["<script>x</script>"]}]}'
    built = html.build(raw, [])

    assert built.primary_mime == "text/html"
    body = built.primary.decode()
    assert "<script>" not in body
    assert "&lt;script&gt;" in body
