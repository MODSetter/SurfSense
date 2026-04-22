"""Unit tests for resume page-limit helpers and enforcement flow."""

import io
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pypdf
import pytest

from app.agents.new_chat.tools import resume as resume_tool

pytestmark = pytest.mark.unit


class _FakeReport:
    _next_id = 1000

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
        self.id = None


class _FakeSession:
    def __init__(self, parent_report=None):
        self.parent_report = parent_report
        self.added: list[_FakeReport] = []

    async def get(self, _model, _id):
        return self.parent_report

    def add(self, report):
        self.added.append(report)

    async def commit(self):
        for report in self.added:
            if getattr(report, "id", None) is None:
                report.id = _FakeReport._next_id
                _FakeReport._next_id += 1

    async def refresh(self, _report):
        return None


class _SessionContext:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _SessionFactory:
    def __init__(self, sessions):
        self._sessions = list(sessions)

    def __call__(self):
        if not self._sessions:
            raise RuntimeError("No fake sessions left")
        return _SessionContext(self._sessions.pop(0))


def _make_pdf_with_pages(page_count: int) -> bytes:
    writer = pypdf.PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=612, height=792)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def test_count_pdf_pages_reads_compiled_bytes() -> None:
    pdf_bytes = _make_pdf_with_pages(2)
    assert resume_tool._count_pdf_pages(pdf_bytes) == 2


def test_validate_max_pages_rejects_out_of_range() -> None:
    with pytest.raises(ValueError):
        resume_tool._validate_max_pages(0)
    with pytest.raises(ValueError):
        resume_tool._validate_max_pages(6)


@pytest.mark.asyncio
async def test_generate_resume_defaults_to_one_page_target(monkeypatch) -> None:
    read_session = _FakeSession()
    write_session = _FakeSession()
    session_factory = _SessionFactory([read_session, write_session])
    monkeypatch.setattr(resume_tool, "shielded_async_session", session_factory)
    monkeypatch.setattr(resume_tool, "Report", _FakeReport)

    prompts: list[str] = []

    async def _llm_invoke(messages):
        prompts.append(messages[0].content)
        return SimpleNamespace(content="= Jane Doe\n== Experience\n- Built systems")

    llm = SimpleNamespace(ainvoke=AsyncMock(side_effect=_llm_invoke))
    monkeypatch.setattr(
        resume_tool,
        "get_document_summary_llm",
        AsyncMock(return_value=llm),
    )
    monkeypatch.setattr(resume_tool, "_compile_typst", lambda _source: b"pdf")
    monkeypatch.setattr(resume_tool, "_count_pdf_pages", lambda _pdf: 1)

    tool = resume_tool.create_generate_resume_tool(search_space_id=1, thread_id=1)
    result = await tool.ainvoke({"user_info": "Jane Doe experience"})

    assert result["status"] == "ready"
    assert prompts
    assert "**Target Maximum Pages:** 1" in prompts[0]


@pytest.mark.asyncio
async def test_generate_resume_compresses_when_over_limit(monkeypatch) -> None:
    read_session = _FakeSession()
    write_session = _FakeSession()
    session_factory = _SessionFactory([read_session, write_session])
    monkeypatch.setattr(resume_tool, "shielded_async_session", session_factory)
    monkeypatch.setattr(resume_tool, "Report", _FakeReport)

    responses = [
        SimpleNamespace(content="= Jane Doe\n== Experience\n- Detailed bullet 1"),
        SimpleNamespace(content="= Jane Doe\n== Experience\n- Condensed bullet"),
    ]
    llm = SimpleNamespace(ainvoke=AsyncMock(side_effect=responses))
    monkeypatch.setattr(
        resume_tool,
        "get_document_summary_llm",
        AsyncMock(return_value=llm),
    )
    monkeypatch.setattr(resume_tool, "_compile_typst", lambda _source: b"pdf")
    page_counts = iter([2, 1])
    monkeypatch.setattr(resume_tool, "_count_pdf_pages", lambda _pdf: next(page_counts))

    tool = resume_tool.create_generate_resume_tool(search_space_id=1, thread_id=1)
    result = await tool.ainvoke({"user_info": "Jane Doe experience", "max_pages": 1})

    assert result["status"] == "ready"
    assert write_session.added, "Expected successful report write"
    metadata = write_session.added[0].report_metadata
    assert metadata["target_max_pages"] == 1
    assert metadata["actual_page_count"] == 1
    assert metadata["compression_attempts"] == 1
    assert metadata["page_limit_enforced"] is True


@pytest.mark.asyncio
async def test_generate_resume_returns_ready_when_target_not_met(monkeypatch) -> None:
    read_session = _FakeSession()
    write_session = _FakeSession()
    session_factory = _SessionFactory([read_session, write_session])
    monkeypatch.setattr(resume_tool, "shielded_async_session", session_factory)
    monkeypatch.setattr(resume_tool, "Report", _FakeReport)

    responses = [
        SimpleNamespace(content="= Jane Doe\n== Experience\n- Long detail"),
        SimpleNamespace(content="= Jane Doe\n== Experience\n- Still long"),
        SimpleNamespace(content="= Jane Doe\n== Experience\n- Still too long"),
    ]
    llm = SimpleNamespace(ainvoke=AsyncMock(side_effect=responses))
    monkeypatch.setattr(
        resume_tool,
        "get_document_summary_llm",
        AsyncMock(return_value=llm),
    )
    monkeypatch.setattr(resume_tool, "_compile_typst", lambda _source: b"pdf")
    page_counts = iter([3, 3, 2])
    monkeypatch.setattr(resume_tool, "_count_pdf_pages", lambda _pdf: next(page_counts))

    tool = resume_tool.create_generate_resume_tool(search_space_id=1, thread_id=1)
    result = await tool.ainvoke({"user_info": "Jane Doe experience", "max_pages": 1})

    assert result["status"] == "ready"
    assert "could not fit the target" in (result["message"] or "").lower()
    metadata = write_session.added[0].report_metadata
    assert metadata["target_page_met"] is False
    assert metadata["actual_page_count"] == 2


@pytest.mark.asyncio
async def test_generate_resume_fails_when_hard_limit_exceeded(monkeypatch) -> None:
    read_session = _FakeSession()
    failed_session = _FakeSession()
    session_factory = _SessionFactory([read_session, failed_session])
    monkeypatch.setattr(resume_tool, "shielded_async_session", session_factory)
    monkeypatch.setattr(resume_tool, "Report", _FakeReport)

    responses = [
        SimpleNamespace(content="= Jane Doe\n== Experience\n- Long detail"),
        SimpleNamespace(content="= Jane Doe\n== Experience\n- Still long"),
        SimpleNamespace(content="= Jane Doe\n== Experience\n- Still too long"),
    ]
    llm = SimpleNamespace(ainvoke=AsyncMock(side_effect=responses))
    monkeypatch.setattr(
        resume_tool,
        "get_document_summary_llm",
        AsyncMock(return_value=llm),
    )
    monkeypatch.setattr(resume_tool, "_compile_typst", lambda _source: b"pdf")
    page_counts = iter([7, 6, 6])
    monkeypatch.setattr(resume_tool, "_count_pdf_pages", lambda _pdf: next(page_counts))

    tool = resume_tool.create_generate_resume_tool(search_space_id=1, thread_id=1)
    result = await tool.ainvoke({"user_info": "Jane Doe experience", "max_pages": 1})

    assert result["status"] == "failed"
    assert "hard page limit" in (result["error"] or "").lower()
    assert failed_session.added, "Expected failed report persistence"
