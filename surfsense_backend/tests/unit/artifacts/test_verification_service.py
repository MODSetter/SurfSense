from __future__ import annotations

from app.artifacts.verification import service
from app.artifacts.verification.formats.base import (
    FormatAdapter,
    StructuralCheckResult,
)
from app.artifacts.verification.receipt import RECEIPT_PATH, read_receipt
from app.artifacts.verification.render import PreparedPdf
from app.artifacts.verification.vision import VisualReviewResult
from tests.utils.fake_sandbox import FakeSandboxSession

SECRET = "test-secret"
WORKSPACE_ID = 7


def _adapter(result: StructuralCheckResult) -> FormatAdapter:
    return FormatAdapter(
        name="pdf",
        suffix=".pdf",
        convert_to_pdf=False,
        check=lambda _data: result,
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
    assert session.files[RECEIPT_PATH] == b""


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
    assert session.files[RECEIPT_PATH] == b""


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
    assert session.files[RECEIPT_PATH] == b""


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
    assert session.files[RECEIPT_PATH]


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
        raise RuntimeError("LibreOffice conversion failed")

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
    assert session.files[RECEIPT_PATH] == b""
