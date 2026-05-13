"""Unit tests for the vision_llm parser helpers.

Two helpers exist:

- :func:`parse_with_vision_llm` -- single-shot for standalone image
  uploads (.png/.jpg/etc). Returns combined markdown (description +
  verbatim OCR mixed) since the image *is* the document.
- :func:`parse_image_for_description` -- per-image-in-PDF call. Returns
  visual description only; OCR is the ETL service's job.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# parse_with_vision_llm: legacy single-shot path
# ---------------------------------------------------------------------------


async def test_parse_with_vision_llm_returns_combined_markdown(tmp_path):
    """Standalone image uploads still go through the combined-markdown path."""
    from app.etl_pipeline.parsers.vision_llm import parse_with_vision_llm

    img = tmp_path / "scan.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 200)

    fake_response = MagicMock()
    fake_response.content = "# A scan of something."
    fake_llm = AsyncMock()
    fake_llm.ainvoke.return_value = fake_response

    out = await parse_with_vision_llm(str(img), "scan.png", fake_llm)
    assert out == "# A scan of something."
    fake_llm.ainvoke.assert_awaited_once()


async def test_parse_with_vision_llm_rejects_empty_response(tmp_path):
    """An empty model response raises rather than silently returning blanks."""
    from app.etl_pipeline.parsers.vision_llm import parse_with_vision_llm

    img = tmp_path / "scan.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 200)

    fake_response = MagicMock()
    fake_response.content = ""
    fake_llm = AsyncMock()
    fake_llm.ainvoke.return_value = fake_response

    with pytest.raises(ValueError, match="empty content"):
        await parse_with_vision_llm(str(img), "scan.png", fake_llm)


# ---------------------------------------------------------------------------
# parse_image_for_description: per-image-in-PDF, description only
# ---------------------------------------------------------------------------


async def test_parse_image_for_description_returns_description(tmp_path):
    """Description-only path returns the model's markdown unchanged."""
    from app.etl_pipeline.parsers.vision_llm import parse_image_for_description

    img = tmp_path / "scan.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 200)

    fake_response = MagicMock()
    fake_response.content = "Axial CT showing a large cystic mass."
    fake_llm = AsyncMock()
    fake_llm.ainvoke.return_value = fake_response

    out = await parse_image_for_description(str(img), "scan.png", fake_llm)
    assert out == "Axial CT showing a large cystic mass."


async def test_parse_image_for_description_uses_description_only_prompt(tmp_path):
    """The prompt explicitly tells the model NOT to transcribe text.

    This is the contract that lets us drop OCR from the response: the
    ETL pipeline already has the text (from page-level OCR), so asking
    the vision LLM for it would be redundant cost.
    """
    from app.etl_pipeline.parsers.vision_llm import parse_image_for_description

    img = tmp_path / "scan.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 200)

    fake_response = MagicMock()
    fake_response.content = "A description"
    fake_llm = AsyncMock()
    fake_llm.ainvoke.return_value = fake_response

    await parse_image_for_description(str(img), "scan.png", fake_llm)

    # The prompt is the first text part of the message we sent.
    sent_messages = fake_llm.ainvoke.call_args.args[0]
    prompt_text = sent_messages[0].content[0]["text"].lower()
    assert "describe what this image visually depicts" in prompt_text
    assert "do not transcribe text" in prompt_text


async def test_parse_image_for_description_rejects_empty(tmp_path):
    """Empty response surfaces as ValueError so the caller can skip the image."""
    from app.etl_pipeline.parsers.vision_llm import parse_image_for_description

    img = tmp_path / "scan.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 200)

    fake_response = MagicMock()
    fake_response.content = "   "  # whitespace-only counts as empty
    fake_llm = AsyncMock()
    fake_llm.ainvoke.return_value = fake_response

    with pytest.raises(ValueError, match="empty content"):
        await parse_image_for_description(str(img), "scan.png", fake_llm)


# ---------------------------------------------------------------------------
# Image size + extension validation (shared by both paths)
# ---------------------------------------------------------------------------


def test_image_to_data_url_rejects_oversized(tmp_path):
    """Images larger than 5 MB raise before any LLM call is made."""
    from app.etl_pipeline.parsers.vision_llm import _image_to_data_url

    big = tmp_path / "huge.png"
    big.write_bytes(b"\x89PNG" + b"\x00" * (6 * 1024 * 1024))

    with pytest.raises(ValueError, match="Image too large"):
        _image_to_data_url(str(big))


def test_image_to_data_url_rejects_unsupported_extension(tmp_path):
    """Unknown extensions raise rather than guessing a MIME type."""
    from app.etl_pipeline.parsers.vision_llm import _image_to_data_url

    weird = tmp_path / "scan.xyz"
    weird.write_bytes(b"\x00" * 100)

    with pytest.raises(ValueError, match="Unsupported image extension"):
        _image_to_data_url(str(weird))
