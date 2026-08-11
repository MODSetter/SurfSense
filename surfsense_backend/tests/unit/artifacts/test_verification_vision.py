from __future__ import annotations

from types import SimpleNamespace

from app.artifacts.verification import vision
from app.services.billable_calls import QuotaInsufficientError


async def test_review_checks_small_document_in_one_contextual_call(monkeypatch):
    calls = []

    async def fake_invoke_json(_llm, messages, _model):
        calls.append(messages)
        return vision.VisionVerdict()

    monkeypatch.setattr(vision, "invoke_json", fake_invoke_json)
    paths = ("/tmp/page-1.jpg", "/tmp/page-2.jpg")

    result = await vision.review_pages(
        SimpleNamespace(),
        tuple((path, b"jpeg") for path in paths),
    )

    assert result.clean
    assert len(calls) == 1
    assert "flowing document" in calls[0][0].content[0]["text"]


async def test_review_returns_blocking_findings(monkeypatch):
    async def fake_invoke_json(_llm, _messages, _model):
        return vision.VisionVerdict(blocking_findings=["Footer is clipped"])

    monkeypatch.setattr(vision, "invoke_json", fake_invoke_json)

    result = await vision.review_pages(
        SimpleNamespace(),
        (("/tmp/page-1.jpg", b"jpeg"),),
    )

    assert not result.clean
    assert result.findings == ("Footer is clipped",)


async def test_review_keeps_warnings_non_blocking(monkeypatch):
    async def fake_invoke_json(_llm, _messages, _model):
        return vision.VisionVerdict(warnings=["Final page has generous whitespace"])

    monkeypatch.setattr(vision, "invoke_json", fake_invoke_json)

    result = await vision.review_pages(
        SimpleNamespace(),
        (("/tmp/page-1.jpg", b"jpeg"),),
    )

    assert result.clean
    assert not result.findings
    assert result.warnings == ("Final page has generous whitespace",)


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
        return vision.VisionVerdict(blocking_findings=["Footer is clipped"])

    monkeypatch.setattr(vision, "invoke_json", fake_invoke_json)
    paths = tuple(f"/tmp/page-{number}.jpg" for number in range(1, 22))

    result = await vision.review_pages(
        SimpleNamespace(),
        tuple((path, b"jpeg") for path in paths),
    )

    assert not result.clean
    assert result.unavailable_reason is None
    assert "Footer is clipped" in result.findings


async def test_long_document_uses_overlapping_windows(monkeypatch):
    calls = []

    async def fake_invoke_json(_llm, messages, _model):
        calls.append(messages)
        return vision.VisionVerdict()

    monkeypatch.setattr(vision, "invoke_json", fake_invoke_json)
    paths = tuple(f"/tmp/page-{number}.jpg" for number in range(1, 26))

    result = await vision.review_pages(
        SimpleNamespace(),
        tuple((path, b"jpeg") for path in paths),
    )

    assert result.clean
    assert len(calls) == 2
