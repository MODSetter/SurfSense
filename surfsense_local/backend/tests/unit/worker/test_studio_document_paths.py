"""Which path a Word or PDF draft takes, and what its prompt tells the model."""

from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from modules.llm.model_type import ModelType
from modules.llm.models import ProviderConnection, SelectedModel
from modules.llm.profile import Fingerprint, Tier
from modules.llm.resolution import ResolvedGeneration
from worker.studio.office.document import pipeline
from worker.studio.office.document.strength import writes_script
from worker.studio.office.docx import docx
from worker.studio.office.pdf import pdf
from worker.studio.shared import generate
from worker.studio.shared.artifact import Source, SourceImage

pytestmark = pytest.mark.unit


def _model(provider: str, tier: Tier) -> ResolvedGeneration:
    selection = type(
        "Selection",
        (),
        {
            "provider": provider,
            "name": "m",
            "tier": tier,
            "fingerprint": Fingerprint(provider, "m"),
        },
    )()
    return ResolvedGeneration(selection, None)  # type: ignore[arg-type]


def _source(tmp_path: Path) -> Source:
    png = tmp_path / "7-2.png"
    Image.new("RGB", (40, 20), "blue").save(png)
    figure = SourceImage("7-2", "Figure 3: Freight volume by quarter", png)
    return Source(7, "Annual report", "Volume rose.", figures=(figure,))


def _capture(monkeypatch: pytest.MonkeyPatch, reply: str) -> list[str]:
    systems: list[str] = []

    def fake(_model: object, system: str, _sources: object, **_kwargs: Any) -> str:
        systems.append(system)
        return reply

    monkeypatch.setattr(generate, "run_model", fake)
    return systems


def _selected(provider: str, base_url: str | None) -> SelectedModel:
    connection = (
        None
        if base_url is None
        else ProviderConnection(
            label="c", provider="openai_compatible", base_url=base_url
        )
    )
    return SelectedModel(
        model_type=ModelType.TEXT_GEN,
        provider=provider,
        name="qwen3-32b",
        connection=connection,
    )


@pytest.mark.parametrize(
    ("provider", "base_url", "strong"),
    [
        ("llamacpp", None, False),
        ("openai_compatible", "http://localhost:11434/v1", False),  # Ollama
        ("openai_compatible", "http://127.0.0.1:1234/v1", False),  # LM Studio
        ("openai_compatible", "http://[::1]:8080/v1", False),
        ("openai_compatible", "http://LocalHost:11434/v1", False),
        ("openai_compatible", "http://127.0.0.2:8080/v1", False),
        ("openai_compatible", "https://openrouter.ai/api/v1", True),
        # Another computer on the network, as egress and the tier count it.
        ("openai_compatible", "http://192.168.1.20:11434/v1", True),
        ("openai_compatible", "http://0.0.0.0:11434/v1", True),
    ],
)
def test_a_model_served_from_this_computer_is_small_and_a_remote_one_strong(
    provider: str, base_url: str | None, strong: bool
) -> None:
    """The provisional rule: remote is strong, local is small, whatever serves it."""
    assert writes_script(_selected(provider, base_url)) is strong


@pytest.mark.parametrize("tier", list(Tier))
def test_the_markdown_prompt_lists_each_figure_with_its_caption(
    tier: Tier, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every tier's Markdown prompt shows each figure as the reference to write."""
    systems = _capture(monkeypatch, "# Volume\n\n![Freight volume](image:7-2)\n")

    built = pipeline.render(docx, _model("llamacpp", tier), [_source(tmp_path)], None)

    assert "![Figure 3: Freight volume by quarter](image:7-2)" in systems[0]
    assert "```chart" not in systems[0]  # described, not shown as a block to copy
    assert '"type": "bar"' in systems[0]
    assert built.spec is not None and built.spec["images"] == ["7-2"]


@pytest.mark.parametrize("tier", list(Tier))
def test_the_script_prompt_names_each_figure_and_where_to_open_it(
    tier: Tier, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every tier's script prompt names each figure and the runner's contract."""
    systems = _capture(monkeypatch, "")  # no script: nothing reaches the runner

    with pytest.raises(RuntimeError):
        pipeline.render(
            pdf, _model("openai_compatible", tier), [_source(tmp_path)], None
        )

    assert '"7-2": Figure 3: Freight volume by quarter' in systems[0]
    assert "IMAGES_DIR" in systems[0]
    assert "OUTPUT_PATH" in systems[0]
    assert "reportlab" in systems[0]


def test_without_figures_the_prompt_says_to_place_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No figures, no invented image references."""
    systems = _capture(monkeypatch, "# Volume\n")

    pipeline.render(
        docx, _model("llamacpp", Tier.COMPACT), [Source(1, "Notes", "x")], None
    )

    assert "place none" in systems[0]


CHARTED = (
    "# Freight report\n\nVolume rose.\n\n```chart\n"
    '{"type": "bar", "title": "Volume", "labels": ["Q1", "Q2"], '
    '"series": [{"name": "Tonnes", "values": [3, 4]}]}\n```'
)


def _refined(monkeypatch: pytest.MonkeyPatch, reply: str) -> dict[str, Any]:
    from modules.artifacts.script_documents.spec import DocumentSpec
    from modules.artifacts.studio_documents.recipe import Refinement
    from worker.studio.office.document.refine import refine

    monkeypatch.setattr(generate, "complete", lambda *_a, **_k: reply)
    base = DocumentSpec("markdown", CHARTED, "docx", ())
    built = refine(
        docx,
        _model("llamacpp", Tier.CAPABLE),
        Refinement("Shorter", base),
        (),
        "Freight report",
    )
    assert built.spec is not None
    return built.spec


def test_a_reply_fenced_as_long_as_the_request_is_unwrapped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A spec holding a chart is sent in a four-backtick fence; a reply in one is the spec."""
    spec = _refined(monkeypatch, f"````markdown\n{CHARTED}\n````")

    assert spec["text"] == CHARTED


def test_a_note_before_the_fenced_markdown_is_not_kept(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A small model's preamble and sign-off stay out of the document."""
    reply = (
        f"Here is the revised document:\n\n```markdown\n{CHARTED}\n```\n\nLet me know!"
    )

    spec = _refined(monkeypatch, reply)

    assert spec["text"] == CHARTED
