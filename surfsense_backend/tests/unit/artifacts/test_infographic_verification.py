from __future__ import annotations

from io import BytesIO

import pytest
from PIL import Image, ImageDraw

from app.artifacts.infographic.generation import normalize_infographic_png
from app.artifacts.infographic.presets import QUESTION_PRESET_ID, resolve_visual_style
from app.artifacts.infographic.selection import (
    issue_selection_token,
    read_selection_token,
)
from app.artifacts.verification import service
from app.artifacts.verification.formats.infographic import (
    check_infographic_markdown,
    check_infographic_png,
)
from app.artifacts.verification.formats.registry import get_format_adapter
from app.artifacts.verification.receipt import read_receipt
from app.artifacts.verification.vision import VisualReviewResult
from tests.utils.fake_sandbox import FakeSandboxSession


def _png(*, transparent: bool = False, blank: bool = False) -> bytes:
    mode = "RGBA" if transparent else "RGB"
    color = (255, 255, 255, 0) if transparent else (255, 255, 255)
    image = Image.new(mode, (640, 480), color)
    if not blank:
        draw = ImageDraw.Draw(image)
        fill = (20, 90, 180, 255) if transparent else (20, 90, 180)
        draw.rectangle((50, 50, 300, 300), fill=fill)
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def test_infographic_adapter_owns_png_visual_and_markdown_policy() -> None:
    adapter = get_format_adapter("infographic")

    assert adapter.suffix == ".png"
    assert adapter.mime_type == "image/png"
    assert adapter.requires_visual_review
    assert adapter.visual_source == "image"
    assert adapter.requires_markdown_binding
    assert adapter.markdown_check is check_infographic_markdown


def test_infographic_programmatic_checks_reject_blank_and_truncated_png() -> None:
    assert check_infographic_png(_png()).clean
    assert check_infographic_png(_png(blank=True)).findings
    assert "complete PNG" in check_infographic_png(_png()[:-8]).findings[0]


def test_infographic_markdown_requires_title_and_sections() -> None:
    assert check_infographic_markdown(b"# Water cycle\n\n## Evaporation\nWater rises.").clean
    assert check_infographic_markdown(b"Water cycle").findings
    assert check_infographic_markdown(b"# Water cycle").findings


def test_normalization_produces_rgb_png_and_rejects_transparency() -> None:
    normalized, width, height = normalize_infographic_png(_png())

    assert normalized.startswith(b"\x89PNG\r\n\x1a\n")
    assert (width, height) == (640, 480)
    with Image.open(BytesIO(normalized)) as image:
        assert image.mode == "RGB"

    with pytest.raises(ValueError, match="transparent"):
        normalize_infographic_png(_png(transparent=True))


def test_selection_token_is_bound_to_workspace_thread_and_expiry() -> None:
    resolved = resolve_visual_style("auto", "friendly guide for children")
    token = issue_selection_token(
        workspace_id=7,
        thread_id=11,
        preset_id=QUESTION_PRESET_ID,
        preset_version=1,
        resolved=resolved,
        secret_key="test-secret",
        now=100,
    )

    parsed = read_selection_token(
        token,
        workspace_id=7,
        thread_id=11,
        secret_key="test-secret",
        now=101,
    )
    assert parsed.requested_style_id == "auto"
    assert parsed.resolved_style_id == "kawaii"

    with pytest.raises(ValueError, match="another workspace"):
        read_selection_token(
            token,
            workspace_id=8,
            thread_id=11,
            secret_key="test-secret",
            now=101,
        )
    with pytest.raises(ValueError, match="expired"):
        read_selection_token(
            token,
            workspace_id=7,
            thread_id=11,
            secret_key="test-secret",
            now=4_000,
        )


async def test_visual_verification_binds_hashes_and_sanitized_provenance(
    monkeypatch,
) -> None:
    path = "/workspace/guide.png"
    markdown_path = "/workspace/guide.md"
    markdown = b"# Guide\n\n## First step\nDo the first thing."
    session = FakeSandboxSession({path: _png(), markdown_path: markdown})

    async def clean_review(*_args, **_kwargs):
        assert "First step" in _kwargs["reference_text"]
        return VisualReviewResult(clean=True, findings=())

    monkeypatch.setattr(service, "review_pages", clean_review)
    provenance = {
        "question_preset_id": QUESTION_PRESET_ID,
        "question_preset_version": 1,
        "requested_style_id": "auto",
        "resolved_style_id": "sketch-note",
        "image_gen_model_id": 17,
        "provider_model": "provider/model",
        "width": 640,
        "height": 480,
    }

    result = await service.verify_artifact(
        session,
        path,
        format="infographic",
        workspace_id=7,
        vision_llm=object(),
        markdown_path=markdown_path,
        visual_reference=markdown.decode(),
        provenance=provenance,
        secret_key="test-secret",
    )

    assert result.verified
    receipt = await read_receipt(
        session,
        "test-secret",
        workspace_id=7,
        primary_path=path,
    )
    assert receipt.markdown_representation_sha256 is not None
    assert receipt.provenance == provenance


async def test_infographic_fails_closed_without_visual_model() -> None:
    path = "/workspace/guide.png"
    markdown_path = "/workspace/guide.md"
    session = FakeSandboxSession(
        {
            path: _png(),
            markdown_path: b"# Guide\n\n## First step\nDo the first thing.",
        }
    )

    result = await service.verify_artifact(
        session,
        path,
        format="infographic",
        workspace_id=7,
        vision_llm=None,
        markdown_path=markdown_path,
        secret_key="test-secret",
    )

    assert not result.verified
    assert "vision-capable model" in result.findings[0]
