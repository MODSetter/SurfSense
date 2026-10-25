"""Studio's Web page: a model at the agent's bar writes the page; any other fills the template."""

from typing import Any

import pytest

from modules.artifacts.web_pages.no_network import NO_NETWORK_POLICY
from modules.llm.profile import Fingerprint, Tier
from modules.llm.resolution import ResolvedGeneration
from worker.studio.shared import generate
from worker.studio.shared.artifact import Source
from worker.studio.web.html import pipeline as html
from worker.studio.web.html.written import page as written

pytestmark = pytest.mark.unit

META = f'<meta http-equiv="Content-Security-Policy" content="{NO_NETWORK_POLICY}">'
PAGE = (
    '<!doctype html><html lang="en"><head><title>Freight in 2026</title></head>'
    "<body><h1>Freight volume rose</h1><p>Volume rose 8% in Q3.</p>"
    "<script>document.body.dataset.ready = '1'</script></body></html>"
)
SOURCES = [Source(7, "Annual report", "Volume rose 8% in Q3.")]


def _model(provider: str, tier: Tier = Tier.FRONTIER) -> ResolvedGeneration:
    selection = type(
        "Selection",
        (),
        {
            "provider": provider,
            "name": "m",
            "connection": None,
            "tier": tier,
            "fingerprint": Fingerprint(provider, "m"),
        },
    )()
    return ResolvedGeneration(selection, None)  # type: ignore[arg-type]


def _replies(monkeypatch: pytest.MonkeyPatch, *replies: str) -> list[dict[str, Any]]:
    """The model answers each call with the next reply; each call's system and repair are kept."""
    calls: list[dict[str, Any]] = []
    queue = list(replies)

    def fake(_model: object, system: str, _sources: object, **kwargs: Any) -> str:
        calls.append({"system": system, "repair": kwargs.get("repair")})
        return queue.pop(0)

    monkeypatch.setattr(generate, "run_model", fake)
    return calls


def test_a_model_below_the_bar_fills_the_template(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A model served from this computer and not measured keeps today's JSON page."""
    calls = _replies(
        monkeypatch,
        '{"title": "T", "sections": [{"heading": "H", "paragraphs": ["p"]}]}',
    )

    built = html.render(_model("llamacpp"), SOURCES, None)

    assert "Return only JSON" in calls[0]["system"]
    assert built.primary.decode().startswith("<!doctype html>\n<html")


def test_a_model_at_the_bar_writes_the_page_from_the_design_guide(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Its prompt carries the guide and the user's focus; its page is kept as written."""
    calls = _replies(monkeypatch, PAGE)

    built = html.render(_model("openai"), SOURCES, "for the board")

    system = calls[0]["system"]
    assert "How a page looks and moves" in system
    assert "for the board" in system
    assert built.primary.decode() == PAGE.replace(
        "<!doctype html>", "<!doctype html>" + META, 1
    )
    assert built.title == "Freight in 2026"
    assert built.markdown == "# Freight volume rose\n\nVolume rose 8% in Q3."
    assert (built.primary_mime, built.primary_filename) == (
        "text/html",
        "Freight in 2026.html",
    )
    # Kept as the model wrote it, without the policy, so a Refine rewrites the page's words.
    assert built.spec == {"kind": "html", "text": PAGE, "format": "html", "images": []}


def test_a_page_in_a_code_fence_is_taken_out_of_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Models often fence their answer; the fence is not part of the page."""
    _replies(monkeypatch, f"Here is the page:\n\n```html\n{PAGE}\n```\n")

    built = html.render(_model("openai"), SOURCES, None)

    assert built.primary.decode().startswith("<!doctype html>" + META + "<html")
    assert built.primary.decode().endswith("</html>")


def test_a_page_cut_off_is_sent_back_to_be_finished(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A reply that ran out before </html> is a failure the model is shown."""
    calls = _replies(monkeypatch, PAGE[:120], PAGE)

    built = html.render(_model("openai"), SOURCES, None)

    assert built.title == "Freight in 2026"
    assert calls[1]["repair"] is not None
    assert "</html>" in calls[1]["repair"].instruction


def test_three_failed_pages_fail_the_job_with_the_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """It never falls back to the template, which would hide the failure."""
    calls = _replies(monkeypatch, "no page at all", "still none", "nothing")

    with pytest.raises(written.PageDraftFailedError) as failed:
        html.render(_model("openai"), SOURCES, None)

    assert len(calls) == 3
    assert "no HTML" in str(failed.value)


def test_a_page_too_large_is_sent_back_to_be_made_smaller(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One reply's limit, well under the agent's, since Studio writes it in one go."""
    monkeypatch.setattr(written, "PAGE_BYTES", 1000)
    big = PAGE.replace("<p>", "<p>" + "x" * 1000)
    calls = _replies(monkeypatch, big, PAGE)

    html.render(_model("openai"), SOURCES, None)

    assert "larger than" in calls[1]["repair"].instruction


SAMPLE = "<pre><code>```\nprint(1)\n```</code></pre>"
WITH_SAMPLE = PAGE.replace("</body>", SAMPLE + "</body>")


@pytest.mark.parametrize(
    "reply",
    [WITH_SAMPLE, f"Here it is:\n\n```html\n{WITH_SAMPLE}\n```\n"],
    ids=["unfenced", "fenced"],
)
def test_a_page_with_a_code_sample_in_it_is_taken_whole(reply: str) -> None:
    """Backticks inside the page are part of it, whether or not the reply fences the page."""
    assert written.reply_page(reply) == WITH_SAMPLE


def test_prose_naming_an_html_tag_before_the_page_is_not_part_of_it() -> None:
    """The page starts at its doctype, not at a tag the model mentioned first."""
    reply = f"I kept the <html> element's lang attribute.\n\n```html\n{PAGE}\n```"
    assert written.reply_page(reply) == PAGE
