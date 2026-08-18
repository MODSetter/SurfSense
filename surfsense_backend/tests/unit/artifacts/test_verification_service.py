from __future__ import annotations

import asyncio

from app.artifacts.verification import service
from app.artifacts.verification.formats.base import (
    FormatAdapter,
    StructuralCheckResult,
)
from app.artifacts.verification.receipt import (
    preview_path,
    read_receipt,
    receipt_path,
)
from app.artifacts.verification.render import ArtifactRenderError, PreparedPdf
from app.artifacts.verification.vision import VisualReviewResult
from tests.utils.fake_sandbox import FakeSandboxSession

SECRET = "test-secret"
WORKSPACE_ID = 7


def test_public_verification_error_hides_internal_details():
    detail = "https://provider.invalid request_id=secret"

    assert detail not in service._public_verification_error(RuntimeError(detail))
    assert "missing" in service._public_verification_error(
        FileNotFoundError("/workspace/report.pdf")
    )


def _adapter(
    result: StructuralCheckResult,
    *,
    convert_to_pdf: bool = False,
    expects_exact_page_count: bool = False,
    rendered_min_chars: int = 20,
) -> FormatAdapter:
    return FormatAdapter(
        name="pdf",
        suffix=".pdf",
        mime_type="application/pdf",
        convert_to_pdf=convert_to_pdf,
        check=lambda _data: result,
        expects_exact_page_count=expects_exact_page_count,
        rendered_min_chars=rendered_min_chars,
    )


async def test_structural_failure_produces_no_receipt(monkeypatch):
    session = FakeSandboxSession({"/workspace/report.pdf": b"pdf"})
    monkeypatch.setattr(
        service,
        "get_format_adapter",
        lambda _path: _adapter(StructuralCheckResult(("page is blank",), 1)),
    )

    result = await service.verify_artifact(
        session,
        "/workspace/report.pdf",
        workspace_id=WORKSPACE_ID,
        vision_llm=object(),
        secret_key=SECRET,
    )

    assert not result.verified
    assert result.findings == ("page is blank",)
    assert session.files[receipt_path("/workspace/report.pdf")] == b""


async def test_page_ceiling_stops_before_rasterization(monkeypatch):
    session = FakeSandboxSession({"/workspace/report.pdf": b"pdf"})
    clean = StructuralCheckResult(
        (),
        service.ARTIFACT_MAX_VERIFY_PAGES + 1,
    )
    monkeypatch.setattr(service, "get_format_adapter", lambda _path: _adapter(clean))

    async def prepare(*_args, **_kwargs):
        return PreparedPdf(
            "/tmp/build",
            "/workspace/report.pdf",
            "/workspace/report.pdf",
        )

    async def rasterize(*_args, **_kwargs):
        raise AssertionError("page ceiling was checked after rasterization")

    monkeypatch.setattr(service, "prepare_pdf", prepare)
    monkeypatch.setattr(service, "rasterize_pdf", rasterize)

    result = await service.verify_artifact(
        session,
        "/workspace/report.pdf",
        workspace_id=WORKSPACE_ID,
        vision_llm=object(),
        secret_key=SECRET,
    )

    assert not result.verified
    assert "at most" in result.findings[0]
    assert session.files[receipt_path("/workspace/report.pdf")] == b""


async def test_failing_visual_verdict_produces_no_receipt(monkeypatch):
    session = FakeSandboxSession(
        {
            "/workspace/report.pdf": b"pdf",
            "/tmp/build/page-1.jpg": b"jpeg",
        }
    )
    clean = StructuralCheckResult((), 1)
    monkeypatch.setattr(service, "get_format_adapter", lambda _path: _adapter(clean))
    monkeypatch.setattr(service, "check_pdf", lambda _data: clean)

    async def prepare(*_args, **_kwargs):
        return PreparedPdf(
            "/tmp/build",
            "/workspace/report.pdf",
            "/workspace/report.pdf",
        )

    async def rasterize(*_args, **_kwargs):
        return ("/tmp/build/page-1.jpg",)

    async def review(*_args, **_kwargs):
        return VisualReviewResult(False, ("Footer is clipped",))

    monkeypatch.setattr(service, "prepare_pdf", prepare)
    monkeypatch.setattr(service, "rasterize_pdf", rasterize)
    monkeypatch.setattr(service, "review_pages", review)

    result = await service.verify_artifact(
        session,
        "/workspace/report.pdf",
        workspace_id=WORKSPACE_ID,
        vision_llm=object(),
        secret_key=SECRET,
    )

    assert not result.verified
    assert result.findings == ("Footer is clipped",)
    assert session.files[receipt_path("/workspace/report.pdf")] == b""


async def test_visual_warnings_are_advisory(monkeypatch):
    session = FakeSandboxSession(
        {
            "/workspace/report.pdf": b"pdf",
            "/tmp/build/page-1.jpg": b"jpeg",
        }
    )
    clean = StructuralCheckResult((), 1)
    monkeypatch.setattr(service, "get_format_adapter", lambda _path: _adapter(clean))
    monkeypatch.setattr(service, "check_pdf", lambda _data: clean)

    async def prepare(*_args, **_kwargs):
        return PreparedPdf(
            "/tmp/build",
            "/workspace/report.pdf",
            "/workspace/report.pdf",
        )

    async def rasterize(*_args, **_kwargs):
        return ("/tmp/build/page-1.jpg",)

    async def review(*_args, **_kwargs):
        return VisualReviewResult(
            True,
            (),
            warnings=("Final page has generous whitespace",),
        )

    monkeypatch.setattr(service, "prepare_pdf", prepare)
    monkeypatch.setattr(service, "rasterize_pdf", rasterize)
    monkeypatch.setattr(service, "review_pages", review)

    result = await service.verify_artifact(
        session,
        "/workspace/report.pdf",
        workspace_id=WORKSPACE_ID,
        vision_llm=object(),
        secret_key=SECRET,
    )

    assert result.verified
    assert result.notes == ("Final page has generous whitespace",)
    assert session.files[receipt_path("/workspace/report.pdf")]


async def test_unavailable_vision_issues_receipt_with_reason(monkeypatch):
    session = FakeSandboxSession(
        {
            "/workspace/report.pdf": b"pdf",
            "/tmp/build/page-1.jpg": b"jpeg",
        }
    )
    clean = StructuralCheckResult((), 1)
    monkeypatch.setattr(service, "get_format_adapter", lambda _path: _adapter(clean))
    monkeypatch.setattr(service, "check_pdf", lambda _data: clean)

    async def prepare(*_args, **_kwargs):
        return PreparedPdf(
            "/tmp/build",
            "/workspace/report.pdf",
            "/workspace/report.pdf",
        )

    async def rasterize(*_args, **_kwargs):
        return ("/tmp/build/page-1.jpg",)

    monkeypatch.setattr(service, "prepare_pdf", prepare)
    monkeypatch.setattr(service, "rasterize_pdf", rasterize)

    result = await service.verify_artifact(
        session,
        "/workspace/report.pdf",
        workspace_id=WORKSPACE_ID,
        vision_llm=None,
        secret_key=SECRET,
    )
    receipt = await read_receipt(
        session,
        SECRET,
        workspace_id=WORKSPACE_ID,
        primary_path="/workspace/report.pdf",
    )

    assert result.verified
    assert result.unavailable_reason
    assert receipt.visual == "unavailable"
    assert receipt.primary_sha256


async def test_conversion_failure_returns_failed_verdict(monkeypatch):
    session = FakeSandboxSession({"/workspace/report.pdf": b"pdf"})
    clean = StructuralCheckResult((), 1)
    monkeypatch.setattr(service, "get_format_adapter", lambda _path: _adapter(clean))

    async def prepare(*_args, **_kwargs):
        raise ArtifactRenderError("LibreOffice conversion failed")

    monkeypatch.setattr(service, "prepare_pdf", prepare)

    result = await service.verify_artifact(
        session,
        "/workspace/report.pdf",
        workspace_id=WORKSPACE_ID,
        vision_llm=None,
        secret_key=SECRET,
    )

    assert not result.verified
    assert "LibreOffice conversion failed" in result.findings[0]
    assert session.files[receipt_path("/workspace/report.pdf")] == b""


async def test_converted_page_count_must_match_structural_count(monkeypatch):
    session = FakeSandboxSession(
        {
            "/workspace/deck.pptx": b"pptx",
            "/tmp/build/primary.pdf": b"pdf",
        }
    )
    clean = StructuralCheckResult((), 2)
    monkeypatch.setattr(
        service,
        "get_format_adapter",
        lambda _path: _adapter(
            clean,
            convert_to_pdf=True,
            expects_exact_page_count=True,
            rendered_min_chars=0,
        ),
    )

    async def prepare(*_args, **_kwargs):
        return PreparedPdf(
            "/tmp/build",
            "/tmp/build/primary.pptx",
            "/tmp/build/primary.pdf",
        )

    def check_rendered(_data, *, expected_pages, min_chars):
        assert expected_pages == 2
        assert min_chars == 0
        return StructuralCheckResult(("expected 2 page(s), found 1",), 1)

    monkeypatch.setattr(service, "prepare_pdf", prepare)
    monkeypatch.setattr(service, "check_pdf", check_rendered)

    result = await service.verify_artifact(
        session,
        "/workspace/deck.pptx",
        workspace_id=WORKSPACE_ID,
        vision_llm=None,
        secret_key=SECRET,
    )

    assert not result.verified
    assert result.findings == ("expected 2 page(s), found 1",)
    assert session.files[receipt_path("/workspace/deck.pptx")] == b""


async def test_converted_preview_is_stable_and_temporary_files_are_cleaned(
    monkeypatch,
):
    path = "/workspace/report.docx"
    prepared = PreparedPdf(
        "/tmp/build-unique",
        "/tmp/build-unique/primary.docx",
        "/tmp/build-unique/primary.pdf",
        "/tmp/profile-unique",
    )
    session = FakeSandboxSession(
        {
            path: b"docx",
            prepared.source_path: b"docx",
            prepared.pdf_path: b"pdf",
            "/tmp/build-unique/page-1.jpg": b"jpeg",
        }
    )
    clean = StructuralCheckResult((), 1)
    monkeypatch.setattr(
        service,
        "get_format_adapter",
        lambda _path: _adapter(clean, convert_to_pdf=True, rendered_min_chars=0),
    )

    async def prepare(*_args, **_kwargs):
        return prepared

    monkeypatch.setattr(service, "prepare_pdf", prepare)
    monkeypatch.setattr(service, "check_pdf", lambda *_args, **_kwargs: clean)

    async def rasterize(*_args, **_kwargs):
        return ("/tmp/build-unique/page-1.jpg",)

    monkeypatch.setattr(service, "rasterize_pdf", rasterize)

    result = await service.verify_artifact(
        session,
        path,
        workspace_id=WORKSPACE_ID,
        vision_llm=None,
        secret_key=SECRET,
    )
    receipt = await read_receipt(
        session,
        SECRET,
        workspace_id=WORKSPACE_ID,
        primary_path=path,
    )

    assert result.preview_path == preview_path(path)
    assert receipt.preview_path == preview_path(path)
    assert session.files[preview_path(path)] == b"pdf"
    assert any(
        command == "rm -rf -- /tmp/build-unique /tmp/profile-unique"
        for command in session.commands
    )


async def test_failed_reverification_invalidates_receipt_and_preview(monkeypatch):
    path = "/workspace/report.docx"
    staged_preview = preview_path(path)
    session = FakeSandboxSession({path: b"changed", staged_preview: b"old-preview"})
    await service.write_receipt(
        session,
        service.VerificationReceipt(
            workspace_id=WORKSPACE_ID,
            session_id=session.session_id,
            format="pdf",
            primary_path=path,
            primary_sha256="a" * 64,
            preview_path=staged_preview,
            preview_sha256="b" * 64,
            page_count=1,
            visual="clean",
            issued_at=int(service.time.time()),
        ),
        SECRET,
    )
    monkeypatch.setattr(
        service,
        "get_format_adapter",
        lambda _path: _adapter(StructuralCheckResult(("broken",), 1)),
    )

    result = await service.verify_artifact(
        session,
        path,
        workspace_id=WORKSPACE_ID,
        vision_llm=None,
        secret_key=SECRET,
    )

    assert not result.verified
    assert session.files[receipt_path(path)] == b""
    assert session.files[staged_preview] == b""


async def test_verification_serializes_same_path_but_not_distinct_paths(monkeypatch):
    session = FakeSandboxSession(
        {
            "/workspace/a.pdf": b"a",
            "/workspace/b.pdf": b"b",
        }
    )
    active_by_path: dict[str, int] = {}
    max_by_path: dict[str, int] = {}
    total_active = 0
    max_total = 0

    async def verify(_session, path, **_kwargs):
        nonlocal total_active, max_total
        active_by_path[path] = active_by_path.get(path, 0) + 1
        max_by_path[path] = max(max_by_path.get(path, 0), active_by_path[path])
        total_active += 1
        max_total = max(max_total, total_active)
        await asyncio.sleep(0.02)
        active_by_path[path] -= 1
        total_active -= 1
        return service.VerificationResult(True, ())

    monkeypatch.setattr(service, "_verify_artifact", verify)

    await asyncio.gather(
        service.verify_artifact(
            session,
            "/workspace/a.pdf",
            workspace_id=WORKSPACE_ID,
            vision_llm=None,
            secret_key=SECRET,
        ),
        service.verify_artifact(
            session,
            "/workspace/a.pdf",
            workspace_id=WORKSPACE_ID,
            vision_llm=None,
            secret_key=SECRET,
        ),
        service.verify_artifact(
            session,
            "/workspace/b.pdf",
            workspace_id=WORKSPACE_ID,
            vision_llm=None,
            secret_key=SECRET,
        ),
    )

    assert max_by_path == {"/workspace/a.pdf": 1, "/workspace/b.pdf": 1}
    assert max_total == 2
