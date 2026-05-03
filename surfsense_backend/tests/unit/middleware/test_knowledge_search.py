"""Unit tests for knowledge_search middleware helpers."""

import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.agents.new_chat.document_xml import build_document_xml as _build_document_xml
from app.agents.new_chat.middleware.knowledge_search import (
    KBSearchPlan,
    KnowledgeBaseSearchMiddleware,
    _normalize_optional_date_range,
    _parse_kb_search_plan_response,
    _render_recent_conversation,
    _resolve_search_types,
)

pytestmark = pytest.mark.unit


# ── _resolve_search_types ──────────────────────────────────────────────


class TestResolveSearchTypes:
    def test_returns_none_when_no_inputs(self):
        assert _resolve_search_types(None, None) is None

    def test_returns_none_when_both_empty(self):
        assert _resolve_search_types([], []) is None

    def test_includes_legacy_type_for_google_gmail(self):
        result = _resolve_search_types(["GOOGLE_GMAIL_CONNECTOR"], None)
        assert "GOOGLE_GMAIL_CONNECTOR" in result
        assert "COMPOSIO_GMAIL_CONNECTOR" in result

    def test_includes_legacy_type_for_google_drive(self):
        result = _resolve_search_types(None, ["GOOGLE_DRIVE_FILE"])
        assert "GOOGLE_DRIVE_FILE" in result
        assert "COMPOSIO_GOOGLE_DRIVE_CONNECTOR" in result

    def test_includes_legacy_type_for_google_calendar(self):
        result = _resolve_search_types(["GOOGLE_CALENDAR_CONNECTOR"], None)
        assert "GOOGLE_CALENDAR_CONNECTOR" in result
        assert "COMPOSIO_GOOGLE_CALENDAR_CONNECTOR" in result

    def test_no_legacy_expansion_for_unrelated_types(self):
        result = _resolve_search_types(["FILE", "NOTE"], None)
        assert set(result) == {"FILE", "NOTE"}

    def test_combines_connectors_and_document_types(self):
        result = _resolve_search_types(["FILE"], ["NOTE", "CRAWLED_URL"])
        assert {"FILE", "NOTE", "CRAWLED_URL"}.issubset(set(result))

    def test_deduplicates(self):
        result = _resolve_search_types(["FILE", "FILE"], ["FILE"])
        assert result.count("FILE") == 1


# ── _build_document_xml ────────────────────────────────────────────────


class TestBuildDocumentXml:
    @pytest.fixture
    def sample_document(self):
        return {
            "document_id": 42,
            "document": {
                "id": 42,
                "document_type": "FILE",
                "title": "Test Doc",
                "metadata": {"url": "https://example.com"},
            },
            "chunks": [
                {"chunk_id": 101, "content": "First chunk content"},
                {"chunk_id": 102, "content": "Second chunk content"},
                {"chunk_id": 103, "content": "Third chunk content"},
            ],
        }

    def test_contains_document_metadata(self, sample_document):
        xml = _build_document_xml(sample_document)
        assert "<document_id>42</document_id>" in xml
        assert "<document_type>FILE</document_type>" in xml
        assert "Test Doc" in xml

    def test_contains_chunk_index(self, sample_document):
        xml = _build_document_xml(sample_document)
        assert "<chunk_index>" in xml
        assert "</chunk_index>" in xml
        assert 'chunk_id="101"' in xml
        assert 'chunk_id="102"' in xml
        assert 'chunk_id="103"' in xml

    def test_matched_chunks_flagged_in_index(self, sample_document):
        xml = _build_document_xml(sample_document, matched_chunk_ids={101, 103})
        lines = xml.split("\n")
        for line in lines:
            if 'chunk_id="101"' in line:
                assert 'matched="true"' in line
            if 'chunk_id="102"' in line:
                assert 'matched="true"' not in line
            if 'chunk_id="103"' in line:
                assert 'matched="true"' in line

    def test_chunk_content_in_document_content_section(self, sample_document):
        xml = _build_document_xml(sample_document)
        assert "<document_content>" in xml
        assert "First chunk content" in xml
        assert "Second chunk content" in xml
        assert "Third chunk content" in xml

    def test_line_numbers_in_chunk_index_are_accurate(self, sample_document):
        """Verify that the line ranges in chunk_index actually point to the right content."""
        xml = _build_document_xml(sample_document, matched_chunk_ids={101})
        xml_lines = xml.split("\n")

        for line in xml_lines:
            if 'chunk_id="101"' in line and "lines=" in line:
                import re

                m = re.search(r'lines="(\d+)-(\d+)"', line)
                assert m, f"No lines= attribute found in: {line}"
                start, _end = int(m.group(1)), int(m.group(2))
                target_line = xml_lines[start - 1]
                assert "101" in target_line
                assert "First chunk content" in target_line
                break
        else:
            pytest.fail("chunk_id=101 entry not found in chunk_index")

    def test_splits_into_lines_correctly(self, sample_document):
        """Each chunk occupies exactly one line (no embedded newlines)."""
        xml = _build_document_xml(sample_document)
        lines = xml.split("\n")
        chunk_lines = [
            line for line in lines if "<![CDATA[" in line and "<chunk" in line
        ]
        assert len(chunk_lines) == 3


# ── planner parsing / date normalization ───────────────────────────────


class TestPlannerHelpers:
    def test_parse_kb_search_plan_response_accepts_plain_json(self):
        plan = _parse_kb_search_plan_response(
            json.dumps(
                {
                    "optimized_query": "ocv meeting decisions summary",
                    "start_date": "2026-03-01",
                    "end_date": "2026-03-31",
                }
            )
        )
        assert plan.optimized_query == "ocv meeting decisions summary"
        assert plan.start_date == "2026-03-01"
        assert plan.end_date == "2026-03-31"

    def test_parse_kb_search_plan_response_accepts_fenced_json(self):
        plan = _parse_kb_search_plan_response(
            """```json
            {"optimized_query":"deel founders guide","start_date":null,"end_date":null}
            ```"""
        )
        assert plan.optimized_query == "deel founders guide"
        assert plan.start_date is None
        assert plan.end_date is None

    def test_normalize_optional_date_range_returns_none_when_absent(self):
        start_date, end_date = _normalize_optional_date_range(None, None)
        assert start_date is None
        assert end_date is None

    def test_normalize_optional_date_range_resolves_single_bound(self):
        start_date, end_date = _normalize_optional_date_range("2026-03-01", None)
        assert start_date is not None
        assert end_date is not None
        assert start_date.date().isoformat() == "2026-03-01"
        assert end_date >= start_date


class FakeLLM:
    def __init__(self, response_text: str):
        self.response_text = response_text
        self.calls: list[dict] = []

    async def ainvoke(self, messages, config=None):
        self.calls.append({"messages": messages, "config": config})
        return AIMessage(content=self.response_text)


class FakeBudgetLLM:
    def __init__(self, *, max_input_tokens: int):
        self._max_input_tokens_value = max_input_tokens

    def _get_max_input_tokens(self) -> int:
        return self._max_input_tokens_value

    def _count_tokens(self, messages) -> int:
        # Deterministic, simple proxy for tests: count characters as tokens.
        return sum(len(msg.get("content", "")) for msg in messages)


class TestKnowledgeBaseSearchMiddlewarePlanner:
    def test_render_recent_conversation_prefers_latest_messages_under_budget(self):
        messages = [
            HumanMessage(content="old user context " * 40),
            AIMessage(content="old assistant answer " * 35),
            HumanMessage(content="recent user context " * 20),
            AIMessage(content="recent assistant answer " * 18),
            HumanMessage(content="latest question"),
        ]

        rendered = _render_recent_conversation(
            messages,
            llm=FakeBudgetLLM(max_input_tokens=900),
            user_text="latest question",
        )

        assert "recent user context" in rendered
        assert "recent assistant answer" in rendered
        assert "latest question" not in rendered
        assert rendered.index("recent user context") < rendered.index(
            "recent assistant answer"
        )

    def test_render_recent_conversation_falls_back_to_legacy_without_budgeting(self):
        messages = [
            HumanMessage(content="message one"),
            AIMessage(content="message two"),
            HumanMessage(content="latest question"),
        ]

        rendered = _render_recent_conversation(
            messages,
            llm=None,
            user_text="latest question",
        )

        assert "user: message one" in rendered
        assert "assistant: message two" in rendered
        assert "latest question" not in rendered

    async def test_middleware_uses_optimized_query_and_dates(self, monkeypatch):
        captured: dict = {}

        async def fake_search_knowledge_base(**kwargs):
            captured.update(kwargs)
            return []

        monkeypatch.setattr(
            "app.agents.new_chat.middleware.knowledge_search.search_knowledge_base",
            fake_search_knowledge_base,
        )

        llm = FakeLLM(
            json.dumps(
                {
                    "optimized_query": "ocv meeting decisions action items",
                    "start_date": "2026-03-01",
                    "end_date": "2026-03-31",
                }
            )
        )
        middleware = KnowledgeBaseSearchMiddleware(llm=llm, search_space_id=37)

        result = await middleware.abefore_agent(
            {
                "messages": [
                    HumanMessage(content="what happened in our OCV meeting last month?")
                ]
            },
            runtime=None,
        )

        assert result is not None
        assert captured["query"] == "ocv meeting decisions action items"
        assert captured["start_date"] is not None
        assert captured["end_date"] is not None
        assert captured["start_date"].date().isoformat() == "2026-03-01"
        assert captured["end_date"].date().isoformat() == "2026-03-31"
        assert llm.calls[0]["config"] == {"tags": ["surfsense:internal"]}

    async def test_middleware_falls_back_when_planner_returns_invalid_json(
        self,
        monkeypatch,
    ):
        captured: dict = {}

        async def fake_search_knowledge_base(**kwargs):
            captured.update(kwargs)
            return []

        monkeypatch.setattr(
            "app.agents.new_chat.middleware.knowledge_search.search_knowledge_base",
            fake_search_knowledge_base,
        )

        middleware = KnowledgeBaseSearchMiddleware(
            llm=FakeLLM("not json"),
            search_space_id=37,
        )

        await middleware.abefore_agent(
            {"messages": [HumanMessage(content="summarize founders guide by deel")]},
            runtime=None,
        )

        assert captured["query"] == "summarize founders guide by deel"
        assert captured["start_date"] is None
        assert captured["end_date"] is None

    async def test_middleware_passes_none_dates_when_planner_returns_nulls(
        self,
        monkeypatch,
    ):
        captured: dict = {}

        async def fake_search_knowledge_base(**kwargs):
            captured.update(kwargs)
            return []

        monkeypatch.setattr(
            "app.agents.new_chat.middleware.knowledge_search.search_knowledge_base",
            fake_search_knowledge_base,
        )

        middleware = KnowledgeBaseSearchMiddleware(
            llm=FakeLLM(
                json.dumps(
                    {
                        "optimized_query": "deel founders guide summary",
                        "start_date": None,
                        "end_date": None,
                    }
                )
            ),
            search_space_id=37,
        )

        await middleware.abefore_agent(
            {"messages": [HumanMessage(content="summarize founders guide by deel")]},
            runtime=None,
        )

        assert captured["query"] == "deel founders guide summary"
        assert captured["start_date"] is None
        assert captured["end_date"] is None

    async def test_middleware_routes_to_recency_browse_when_flagged(
        self,
        monkeypatch,
    ):
        """When the planner sets is_recency_query=true, browse_recent_documents
        is called instead of search_knowledge_base."""
        browse_captured: dict = {}
        search_called = False

        async def fake_browse_recent_documents(**kwargs):
            browse_captured.update(kwargs)
            return []

        async def fake_search_knowledge_base(**kwargs):
            nonlocal search_called
            search_called = True
            return []

        monkeypatch.setattr(
            "app.agents.new_chat.middleware.knowledge_search.browse_recent_documents",
            fake_browse_recent_documents,
        )
        monkeypatch.setattr(
            "app.agents.new_chat.middleware.knowledge_search.search_knowledge_base",
            fake_search_knowledge_base,
        )

        llm = FakeLLM(
            json.dumps(
                {
                    "optimized_query": "latest uploaded file",
                    "start_date": None,
                    "end_date": None,
                    "is_recency_query": True,
                }
            )
        )
        middleware = KnowledgeBaseSearchMiddleware(llm=llm, search_space_id=42)

        result = await middleware.abefore_agent(
            {"messages": [HumanMessage(content="what's my latest file?")]},
            runtime=None,
        )

        assert result is not None
        assert browse_captured["search_space_id"] == 42
        assert not search_called

    async def test_middleware_uses_hybrid_search_when_not_recency(
        self,
        monkeypatch,
    ):
        """When is_recency_query is false (default), hybrid search is used."""
        search_captured: dict = {}
        browse_called = False

        async def fake_browse_recent_documents(**kwargs):
            nonlocal browse_called
            browse_called = True
            return []

        async def fake_search_knowledge_base(**kwargs):
            search_captured.update(kwargs)
            return []

        monkeypatch.setattr(
            "app.agents.new_chat.middleware.knowledge_search.browse_recent_documents",
            fake_browse_recent_documents,
        )
        monkeypatch.setattr(
            "app.agents.new_chat.middleware.knowledge_search.search_knowledge_base",
            fake_search_knowledge_base,
        )

        llm = FakeLLM(
            json.dumps(
                {
                    "optimized_query": "quarterly revenue report analysis",
                    "start_date": None,
                    "end_date": None,
                    "is_recency_query": False,
                }
            )
        )
        middleware = KnowledgeBaseSearchMiddleware(llm=llm, search_space_id=42)

        await middleware.abefore_agent(
            {"messages": [HumanMessage(content="find the quarterly revenue report")]},
            runtime=None,
        )

        assert search_captured["query"] == "quarterly revenue report analysis"
        assert not browse_called


# ── KBSearchPlan schema ────────────────────────────────────────────────


class TestKBSearchPlanSchema:
    def test_is_recency_query_defaults_to_false(self):
        plan = KBSearchPlan(optimized_query="test query")
        assert plan.is_recency_query is False

    def test_is_recency_query_parses_true(self):
        plan = _parse_kb_search_plan_response(
            json.dumps(
                {
                    "optimized_query": "latest uploaded file",
                    "start_date": None,
                    "end_date": None,
                    "is_recency_query": True,
                }
            )
        )
        assert plan.is_recency_query is True
        assert plan.optimized_query == "latest uploaded file"

    def test_missing_is_recency_query_defaults_to_false(self):
        plan = _parse_kb_search_plan_response(
            json.dumps(
                {
                    "optimized_query": "meeting notes",
                    "start_date": None,
                    "end_date": None,
                }
            )
        )
        assert plan.is_recency_query is False


# ── mentioned_document_ids cross-turn drain ────────────────────────────


class TestKnowledgePriorityMentionDrain:
    """Regression tests for the cross-turn ``mentioned_document_ids`` drain.

    The compiled-agent cache reuses a single :class:`KnowledgePriorityMiddleware`
    instance across turns of the same thread. ``mentioned_document_ids``
    can therefore enter the middleware via two paths:

    1. The constructor closure (``__init__(mentioned_document_ids=...)``) —
       seeded by the cache-miss build on turn 1.
    2. ``runtime.context.mentioned_document_ids`` — supplied freshly per
       turn by the streaming task.

    Without the drain fix, an empty ``runtime.context.mentioned_document_ids``
    on turn 2 would fall through to the closure (because ``[]`` is falsy in
    Python) and replay turn 1's mentions. This class pins down the
    correct behaviour: the runtime path is authoritative even when empty,
    and the closure is drained the first time the runtime path fires so
    no later turn can ever resurrect stale state.
    """

    @staticmethod
    def _make_runtime(mention_ids: list[int]):
        """Minimal runtime stub exposing only ``runtime.context.mentioned_document_ids``."""
        from types import SimpleNamespace

        return SimpleNamespace(
            context=SimpleNamespace(mentioned_document_ids=mention_ids),
        )

    @staticmethod
    def _planner_llm() -> "FakeLLM":
        # Planner returns a stable, non-recency plan so we always land in
        # the hybrid-search branch (where ``fetch_mentioned_documents`` is
        # invoked alongside the main search).
        return FakeLLM(
            json.dumps(
                {
                    "optimized_query": "follow up question",
                    "start_date": None,
                    "end_date": None,
                    "is_recency_query": False,
                }
            )
        )

    async def test_runtime_context_overrides_closure_and_drains_it(self, monkeypatch):
        """Turn 1 with mentions in BOTH closure and runtime context: the
        runtime path wins AND the closure is drained so a future turn
        cannot replay it.
        """
        fetched_ids: list[list[int]] = []

        async def fake_fetch_mentioned_documents(*, document_ids, search_space_id):
            fetched_ids.append(list(document_ids))
            return []

        async def fake_search_knowledge_base(**_kwargs):
            return []

        monkeypatch.setattr(
            "app.agents.new_chat.middleware.knowledge_search.fetch_mentioned_documents",
            fake_fetch_mentioned_documents,
        )
        monkeypatch.setattr(
            "app.agents.new_chat.middleware.knowledge_search.search_knowledge_base",
            fake_search_knowledge_base,
        )

        middleware = KnowledgeBaseSearchMiddleware(
            llm=self._planner_llm(),
            search_space_id=42,
            mentioned_document_ids=[1, 2, 3],
        )

        await middleware.abefore_agent(
            {"messages": [HumanMessage(content="what is in those docs?")]},
            runtime=self._make_runtime([1, 2, 3]),
        )

        assert fetched_ids == [[1, 2, 3]], (
            "runtime.context mentions must be the source of truth on turn 1"
        )
        assert middleware.mentioned_document_ids == [], (
            "closure must be drained the first time the runtime path fires "
            "so no later turn can replay stale mentions"
        )

    async def test_empty_runtime_context_does_not_replay_closure_mentions(
        self, monkeypatch
    ):
        """Regression: turn 2 with NO mentions must not surface turn 1's
        mentions from the constructor closure.

        Before the fix, ``if ctx_mentions:`` treated an empty list as
        absent and fell through to ``elif self.mentioned_document_ids:``,
        replaying turn 1's mentions. This test pins down the corrected
        behaviour.
        """
        fetched_ids: list[list[int]] = []

        async def fake_fetch_mentioned_documents(*, document_ids, search_space_id):
            fetched_ids.append(list(document_ids))
            return []

        async def fake_search_knowledge_base(**_kwargs):
            return []

        monkeypatch.setattr(
            "app.agents.new_chat.middleware.knowledge_search.fetch_mentioned_documents",
            fake_fetch_mentioned_documents,
        )
        monkeypatch.setattr(
            "app.agents.new_chat.middleware.knowledge_search.search_knowledge_base",
            fake_search_knowledge_base,
        )

        # Simulate a cached middleware instance whose closure was seeded
        # by a previous turn's cache-miss build (mentions=[1,2,3]).
        middleware = KnowledgeBaseSearchMiddleware(
            llm=self._planner_llm(),
            search_space_id=42,
            mentioned_document_ids=[1, 2, 3],
        )

        # Turn 2: streaming task supplies an EMPTY mention list (no
        # mentions on this follow-up turn).
        await middleware.abefore_agent(
            {"messages": [HumanMessage(content="what about the next steps?")]},
            runtime=self._make_runtime([]),
        )

        assert fetched_ids == [], (
            "fetch_mentioned_documents must NOT be called when the runtime "
            "context says there are no mentions for this turn"
        )

    async def test_legacy_path_fires_only_when_runtime_context_absent(
        self, monkeypatch
    ):
        """Backward-compat: if a caller doesn't supply runtime.context (old
        non-streaming code path), the closure-injected mentions are still
        honoured exactly once and then drained.
        """
        fetched_ids: list[list[int]] = []

        async def fake_fetch_mentioned_documents(*, document_ids, search_space_id):
            fetched_ids.append(list(document_ids))
            return []

        async def fake_search_knowledge_base(**_kwargs):
            return []

        monkeypatch.setattr(
            "app.agents.new_chat.middleware.knowledge_search.fetch_mentioned_documents",
            fake_fetch_mentioned_documents,
        )
        monkeypatch.setattr(
            "app.agents.new_chat.middleware.knowledge_search.search_knowledge_base",
            fake_search_knowledge_base,
        )

        middleware = KnowledgeBaseSearchMiddleware(
            llm=self._planner_llm(),
            search_space_id=42,
            mentioned_document_ids=[7, 8],
        )

        # First call: no runtime → legacy path uses the closure.
        await middleware.abefore_agent(
            {"messages": [HumanMessage(content="initial question")]},
            runtime=None,
        )
        # Second call: still no runtime — closure already drained, so no replay.
        await middleware.abefore_agent(
            {"messages": [HumanMessage(content="follow up")]},
            runtime=None,
        )

        assert fetched_ids == [[7, 8]], (
            "legacy path must honour the closure exactly once and then drain it"
        )
        assert middleware.mentioned_document_ids == []
