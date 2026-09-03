from __future__ import annotations

import pytest

from app.artifacts.infographic import (
    VISUAL_STYLE_PRESETS,
    VisualStylePreset,
    assemble_infographic_prompt,
    resolve_visual_style,
)


def test_catalog_has_unique_concrete_styles() -> None:
    ids = [preset.id for preset in VISUAL_STYLE_PRESETS]

    assert ids == ["kawaii", "clay", "sketch-note", "anime"]
    assert len(ids) == len(set(ids))
    assert all(preset.description.strip() for preset in VISUAL_STYLE_PRESETS)


@pytest.mark.parametrize(
    ("brief", "expected"),
    [
        ("A friendly guide for children", "kawaii"),
        ("How a handmade product is assembled", "clay"),
        ("Study notes explaining derivatives", "sketch-note"),
        ("A dynamic gaming retrospective", "anime"),
        ("Quarterly company overview", "sketch-note"),
    ],
)
def test_auto_resolution_is_deterministic(brief: str, expected: str) -> None:
    first = resolve_visual_style("auto", brief)
    second = resolve_visual_style("auto", brief)

    assert first.requested_id == "auto"
    assert first.resolved_id == expected
    assert second == first


def test_explicit_style_passes_through() -> None:
    resolved = resolve_visual_style("clay", "study notes for children")

    assert resolved.requested_id == "clay"
    assert resolved.resolved_id == "clay"


def test_unknown_style_fails_closed() -> None:
    with pytest.raises(ValueError, match="Unknown infographic visual style"):
        resolve_visual_style("watercolor", "Anything")


def test_preset_rejects_structurally_invalid_values() -> None:
    with pytest.raises(ValueError, match="lowercase slug"):
        VisualStylePreset(
            id="Sketch Note",
            version=1,
            label="Sketch Note",
            preview_asset="infographic-style/sketch-note",
            description="Draw it.",
        )

    with pytest.raises(ValueError, match="infographic-style namespace"):
        VisualStylePreset(
            id="valid",
            version=1,
            label="Valid",
            preview_asset="https://example.com/preview.png",
            description="Draw it.",
        )


def test_prompt_appends_exact_description_once() -> None:
    style = resolve_visual_style("kawaii", "").preset

    prompt = assemble_infographic_prompt(
        factual_content="Title: Water cycle\n1. Evaporation\n2. Condensation",
        style=style,
        output_constraints="Use a 4:3 canvas.",
    )

    assert prompt.count(style.description) == 1
    assert "Title: Water cycle" in prompt
    assert "Use a 4:3 canvas." in prompt


def test_prompt_appends_repair_findings_without_replacing_facts() -> None:
    style = resolve_visual_style("anime", "").preset

    prompt = assemble_infographic_prompt(
        factual_content="Revenue grew by 20%.",
        style=style,
        repair_findings=["The 20% label is clipped.", "Remove the watermark."],
    )

    assert "Revenue grew by 20%." in prompt
    assert style.description in prompt
    assert "- The 20% label is clipped." in prompt
    assert "- Remove the watermark." in prompt
