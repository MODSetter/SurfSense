from __future__ import annotations

from types import SimpleNamespace

from app.artifacts.verification import vision
from app.services.billable_calls import QuotaInsufficientError


async def test_review_checks_each_page_and_cross_page_window(monkeypatch):
    calls = []

    async def fake_invoke_json(_llm, messages, _model):
        calls.append(messages)
        return vision.VisionVerdict(clean=True)

    monkeypatch.setattr(vision, "invoke_json", fake_invoke_json)
    paths = ("/tmp/page-1.jpg", "/tmp/page-2.jpg")

    result = await vision.review_pages(
        SimpleNamespace(),
        tuple((path, b"jpeg") for path in paths),
    )

    assert result.clean
    assert len(calls) == 3


async def test_review_returns_model_findings(monkeypatch):
    async def fake_invoke_json(_llm, _messages, _model):
        return vision.VisionVerdict(clean=False, findings=["Footer is clipped"])

    monkeypatch.setattr(vision, "invoke_json", fake_invoke_json)

    result = await vision.review_pages(
        SimpleNamespace(),
        (("/tmp/page-1.jpg", b"jpeg"),),
    )

    assert not result.clean
    assert result.findings == ("Footer is clipped",)


async def test_review_never_ignores_findings_marked_clean(monkeypatch):
    async def fake_invoke_json(_llm, _messages, _model):
        return vision.VisionVerdict(clean=True, findings=["Footer is clipped"])

    monkeypatch.setattr(vision, "invoke_json", fake_invoke_json)

    result = await vision.review_pages(
        SimpleNamespace(),
        (("/tmp/page-1.jpg", b"jpeg"),),
    )

    assert not result.clean
    assert result.findings == ("Footer is clipped",)


async def test_review_preserves_quota_unavailable_reason(monkeypatch):
    async def fake_invoke_json(_llm, _messages, _model):
        raise QuotaInsufficientError(
            usage_type="artifact_verification",
            balance_micros=0,
            remaining_micros=0,
        )

    monkeypatch.setattr(vision, "invoke_json", fake_invoke_json)

    result = await vision.review_pages(
        SimpleNamespace(),
        (("/tmp/page-1.jpg", b"jpeg"),),
    )

    assert not result.clean
    assert not result.findings
    assert "credit is insufficient" in (result.unavailable_reason or "")


async def test_known_defect_takes_precedence_over_quota_failure(monkeypatch):
    calls = 0

    async def fake_invoke_json(_llm, _messages, _model):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise QuotaInsufficientError(
                usage_type="artifact_verification",
                balance_micros=0,
                remaining_micros=0,
            )
        return vision.VisionVerdict(clean=False, findings=["Footer is clipped"])

    monkeypatch.setattr(vision, "invoke_json", fake_invoke_json)
    paths = ("/tmp/page-1.jpg", "/tmp/page-2.jpg")

    result = await vision.review_pages(
        SimpleNamespace(),
        tuple((path, b"jpeg") for path in paths),
    )

    assert not result.clean
    assert result.unavailable_reason is None
    assert "Footer is clipped" in result.findings
