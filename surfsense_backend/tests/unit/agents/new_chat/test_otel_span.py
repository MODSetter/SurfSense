"""Tests for the OtelSpanMiddleware adapter."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from app.agents.new_chat.middleware.otel_span import (
    OtelSpanMiddleware,
    _annotate_model_response,
    _annotate_tool_result,
    _resolve_input_size,
    _resolve_model_attrs,
    _resolve_tool_name,
)

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _disable_otel(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.setenv("SURFSENSE_DISABLE_OTEL", "true")
    from app.observability import otel as ot

    ot.reload_for_tests()
    yield
    ot.reload_for_tests()


class TestResolveModelAttrs:
    def test_extracts_model_name_and_provider(self) -> None:
        request = MagicMock()
        request.model = MagicMock(spec=["model_name", "provider"])
        request.model.model_name = "gpt-4o-mini"
        request.model.provider = "openai"
        assert _resolve_model_attrs(request) == ("gpt-4o-mini", "openai")

    def test_handles_missing_model(self) -> None:
        request = MagicMock()
        request.model = None
        assert _resolve_model_attrs(request) == (None, None)

    def test_falls_back_through_attribute_chain(self) -> None:
        request = MagicMock()
        request.model = MagicMock(spec=["model_id", "_llm_type"])
        request.model.model_id = "claude-3-5-sonnet"
        request.model._llm_type = "anthropic-chat"
        model_id, provider = _resolve_model_attrs(request)
        assert model_id == "claude-3-5-sonnet"
        assert provider == "anthropic-chat"


class TestResolveToolName:
    def test_prefers_request_tool_name(self) -> None:
        request = MagicMock()
        request.tool = MagicMock(name="ToolStub")
        request.tool.name = "scrape_webpage"
        assert _resolve_tool_name(request) == "scrape_webpage"

    def test_falls_back_to_tool_call_name(self) -> None:
        request = MagicMock()
        request.tool = None
        request.tool_call = {"name": "web_search", "args": {}}
        assert _resolve_tool_name(request) == "web_search"

    def test_unknown_when_nothing_resolves(self) -> None:
        request = MagicMock()
        request.tool = None
        request.tool_call = {}
        assert _resolve_tool_name(request) == "unknown"


class TestResolveInputSize:
    def test_returns_repr_length_of_args(self) -> None:
        request = MagicMock()
        request.tool_call = {"args": {"query": "hello world"}}
        size = _resolve_input_size(request)
        assert isinstance(size, int)
        assert size > 0

    def test_handles_no_tool_call(self) -> None:
        request = MagicMock()
        request.tool_call = None
        assert _resolve_input_size(request) is None


class TestAnnotateModelResponse:
    def test_attaches_token_counts_when_present(self) -> None:
        sp = MagicMock()
        msg = AIMessage(
            content="hello",
            usage_metadata={
                "input_tokens": 100,
                "output_tokens": 50,
                "total_tokens": 150,
            },
        )
        _annotate_model_response(sp, msg)
        sp.set_attribute.assert_any_call("tokens.prompt", 100)
        sp.set_attribute.assert_any_call("tokens.completion", 50)
        sp.set_attribute.assert_any_call("tokens.total", 150)

    def test_handles_response_with_no_metadata(self) -> None:
        sp = MagicMock()
        msg = AIMessage(content="hello")
        # Should not raise even when usage_metadata is missing
        _annotate_model_response(sp, msg)


class TestAnnotateToolResult:
    def test_records_size_and_status(self) -> None:
        sp = MagicMock()
        result = ToolMessage(
            content="result text",
            tool_call_id="abc",
            status="success",
        )
        _annotate_tool_result(sp, result)
        sp.set_attribute.assert_any_call("tool.output.size", len("result text"))
        sp.set_attribute.assert_any_call("tool.status", "success")

    def test_marks_errors(self) -> None:
        sp = MagicMock()
        result = ToolMessage(
            content="oops",
            tool_call_id="abc",
            additional_kwargs={"error": {"code": "x"}},
        )
        _annotate_tool_result(sp, result)
        sp.set_attribute.assert_any_call("tool.error", True)


@pytest.mark.asyncio
class TestMiddlewareIntegration:
    async def test_awrap_model_call_passes_through_when_disabled(self) -> None:
        mw = OtelSpanMiddleware()
        called: dict[str, Any] = {}

        async def handler(req):
            called["req"] = req
            return AIMessage(content="ok")

        request = MagicMock()
        result = await mw.awrap_model_call(request, handler)
        assert called["req"] is request
        assert isinstance(result, AIMessage)
        assert result.content == "ok"

    async def test_awrap_tool_call_passes_through_when_disabled(self) -> None:
        mw = OtelSpanMiddleware()

        async def handler(req):
            return ToolMessage(content="result", tool_call_id="abc")

        request = MagicMock()
        result = await mw.awrap_tool_call(request, handler)
        assert isinstance(result, ToolMessage)
        assert result.content == "result"

    async def test_awrap_model_call_propagates_exceptions(self) -> None:
        mw = OtelSpanMiddleware()

        async def handler(req):
            raise ValueError("boom")

        with pytest.raises(ValueError):
            await mw.awrap_model_call(MagicMock(), handler)

    async def test_with_otel_enabled_does_not_alter_result(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("SURFSENSE_DISABLE_OTEL", raising=False)
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
        from app.observability import otel as ot

        ot.reload_for_tests()
        try:
            mw = OtelSpanMiddleware()

            async def handler(req):
                return AIMessage(content="enabled")

            request = MagicMock()
            request.model = MagicMock()
            request.model.model_name = "gpt-4o"
            request.model.provider = "openai"
            result = await mw.awrap_model_call(request, handler)
            assert isinstance(result, AIMessage)
            assert result.content == "enabled"
        finally:
            ot.reload_for_tests()
