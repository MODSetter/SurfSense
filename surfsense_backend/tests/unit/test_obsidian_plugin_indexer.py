from __future__ import annotations

import base64
from datetime import UTC, datetime

import pytest

from app.etl_pipeline.etl_document import EtlResult
from app.schemas.obsidian_plugin import HeadingRef, NotePayload
from app.services.obsidian_plugin_indexer import (
    _build_metadata,
    _extract_binary_attachment_markdown,
    _is_image_attachment,
    _require_extracted_attachment_content,
)


def test_build_metadata_serializes_headings_to_plain_json() -> None:
    now = datetime.now(UTC)
    payload = NotePayload(
        vault_id="vault-1",
        path="notes.md",
        name="notes",
        extension="md",
        content="# Notes",
        headings=[HeadingRef(heading="Notes", level=1)],
        content_hash="abc123",
        mtime=now,
        ctime=now,
    )

    metadata = _build_metadata(payload, vault_name="My Vault", connector_id=42)

    assert metadata["headings"] == [{"heading": "Notes", "level": 1}]


def test_build_metadata_marks_binary_attachment_fields() -> None:
    now = datetime.now(UTC)
    payload = NotePayload(
        vault_id="vault-1",
        path="assets/diagram.png",
        name="diagram",
        extension="png",
        content="",
        content_hash="abc123",
        mtime=now,
        ctime=now,
        is_binary=True,
        mime_type="image/png",
    )

    metadata = _build_metadata(payload, vault_name="My Vault", connector_id=42)

    assert metadata["is_binary"] is True
    assert metadata["mime_type"] == "image/png"


@pytest.mark.asyncio
async def test_extract_binary_attachment_markdown_handles_invalid_base64() -> None:
    now = datetime.now(UTC)
    payload = NotePayload(
        vault_id="vault-1",
        path="assets/diagram.png",
        name="diagram",
        extension="png",
        content="",
        content_hash="abc123",
        mtime=now,
        ctime=now,
        is_binary=True,
        binary_base64="not-valid-base64!!",
    )

    content, metadata = await _extract_binary_attachment_markdown(
        payload, vision_llm=None
    )

    assert content == ""
    assert metadata["attachment_extraction_status"] == "invalid_binary_payload"


@pytest.mark.asyncio
async def test_extract_binary_attachment_markdown_uses_etl(monkeypatch) -> None:
    now = datetime.now(UTC)
    payload = NotePayload(
        vault_id="vault-1",
        path="assets/spec.pdf",
        name="spec",
        extension="pdf",
        content="",
        content_hash="abc123",
        mtime=now,
        ctime=now,
        is_binary=True,
        binary_base64=base64.b64encode(b"%PDF-1.7 fake bytes").decode("ascii"),
    )

    async def _fake_run_etl_extract(  # noqa: ANN001
        *, file_path, filename, vision_llm
    ):
        assert filename == "spec.pdf"
        assert file_path
        assert vision_llm is None
        return EtlResult(
            markdown_content="Extracted content",
            etl_service="TEST_ETL",
            content_type="document",
        )

    monkeypatch.setattr(
        "app.services.obsidian_plugin_indexer._run_etl_extract",
        _fake_run_etl_extract,
    )

    content, metadata = await _extract_binary_attachment_markdown(
        payload, vision_llm=None
    )

    assert content == "Extracted content"
    assert metadata["attachment_extraction_status"] == "ok"
    assert metadata["attachment_etl_service"] == "TEST_ETL"


def test_is_image_attachment_detects_image_extensions() -> None:
    now = datetime.now(UTC)
    image_payload = NotePayload(
        vault_id="vault-1",
        path="assets/screenshot.PNG",
        name="screenshot",
        extension="PNG",
        content="",
        content_hash="abc123",
        mtime=now,
        ctime=now,
        is_binary=True,
    )
    pdf_payload = NotePayload(
        vault_id="vault-1",
        path="assets/spec.pdf",
        name="spec",
        extension="pdf",
        content="",
        content_hash="abc123",
        mtime=now,
        ctime=now,
        is_binary=True,
    )

    assert _is_image_attachment(image_payload) is True
    assert _is_image_attachment(pdf_payload) is False


def test_require_extracted_attachment_content_rejects_empty_content() -> None:
    with pytest.raises(
        RuntimeError, match="Attachment extraction failed for assets/img.png"
    ):
        _require_extracted_attachment_content(
            content="   ",
            etl_meta={"attachment_extraction_status": "etl_failed"},
            path="assets/img.png",
        )
