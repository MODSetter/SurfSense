"""Domain telemetry tests: spans are usable no-ops and metrics never raise.

When OTel is disabled every domain span must yield a well-formed no-op and
every metric emitter must be silent, so instrumentation never breaks a request.
"""

from __future__ import annotations

import pytest

from app.observability.core import config
from app.observability.domains import (
    agent,
    celery,
    embedding,
    indexing,
    kb,
    media,
    runtime,
    security,
    speech,
)

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _disabled(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.setenv("SURFSENSE_DISABLE_OTEL", "true")
    config.reload_for_tests()
    yield
    config.reload_for_tests()


class TestDomainSpansAreNoop:
    def test_every_span_yields_a_usable_noop(self) -> None:
        spans = [
            agent.tool_call_span("write_file", input_size=42),
            agent.model_call_span(model_id="openai:gpt-4o", provider="openai"),
            agent.subagent_invoke_span(subagent_type="researcher"),
            agent.compaction_span(reason="overflow", messages_in=120),
            agent.interrupt_span(interrupt_type="permission_ask"),
            agent.permission_asked_span(permission="edit", pattern="/x/**"),
            kb.kb_search_span(workspace_id=1, query_chars=99),
            kb.kb_persist_span(document_type="NOTE", document_id=7),
            kb.rerank_span(document_count=25),
            indexing.connector_sync_span(connector_type="index_notion_pages"),
            embedding.embedding_span(count=8, model="openai:text-embedding-3-small"),
            speech.transcription_span(provider="litellm", model="whisper-1"),
        ]
        for cm in spans:
            with cm as sp:
                assert sp is not None
                sp.set_attribute("ok", True)


class TestDomainMetricsAreNoop:
    def test_every_emitter_is_silent_when_disabled(self) -> None:
        agent.record_model_call_duration(12.5, model="gpt-4o", provider="openai")
        agent.record_model_token_usage(
            input_tokens=10, output_tokens=5, model="gpt-4o", provider="openai"
        )
        agent.record_tool_call_duration(3.0, tool_name="scrape_webpage")
        agent.record_tool_call_error(tool_name="scrape_webpage")
        agent.record_compaction_run(reason="auto")
        agent.record_permission_ask(permission="write_file")
        agent.record_interrupt(interrupt_type="permission_ask")
        kb.record_kb_search_duration(4.0, workspace_id=1, surface="documents")
        kb.record_kb_rerank_duration(6.0, document_count=25)
        embedding.record_embedding_duration(
            9.0, model="openai:text-embedding-3-small", count=8
        )
        speech.record_transcription_duration(7.0, provider="litellm", model="whisper-1")
        speech.record_transcription_duration(2.0, provider="local")
        media.record_media_render(3.5, kind="podcast", status="ready")
        media.record_media_render(
            1.0, kind="video", status="failed", error_category="TIMEOUT"
        )
        indexing.record_indexing_document_duration(1.2, document_type="FILE")
        indexing.record_indexing_document_outcome(document_type="FILE", status="success")
        indexing.record_connector_sync_duration(2.3, connector_type="index_notion_pages")
        indexing.record_connector_sync_outcome(
            connector_type="index_notion_pages", status="success"
        )
        security.record_auth_failure(reason="UNAUTHORIZED")
        security.record_rate_limit_rejection(scope="login")


class TestModelCallGuard:
    """The chokepoint uses ``model_call_active`` to skip re-spanning a call the
    agent middleware already wrapped."""

    def test_active_is_scoped_to_the_span(self) -> None:
        assert agent.model_call_active() is False
        with agent.model_call_span(model_id="openai:gpt-4o"):
            assert agent.model_call_active() is True
        assert agent.model_call_active() is False

    def test_active_resets_on_exception(self) -> None:
        with pytest.raises(RuntimeError), agent.model_call_span(model_id="x"):
            assert agent.model_call_active() is True
            raise RuntimeError("boom")
        assert agent.model_call_active() is False


class TestRuntimeObservables:
    def test_register_is_idempotent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class FakeMeter:
            def __init__(self) -> None:
                self.names: list[str] = []

            def create_observable_gauge(self, name: str, **_kwargs) -> None:
                self.names.append(name)

        fake_meter = FakeMeter()
        monkeypatch.setattr(runtime, "_OBSERVABLES_REGISTERED", False)
        monkeypatch.setattr(config, "_ENABLED", True)
        monkeypatch.setattr(runtime.m, "get_meter", lambda: fake_meter)

        runtime.register_runtime_observables()
        runtime.register_runtime_observables()

        assert len(fake_meter.names) == 6
        assert fake_meter.names.count("python.asyncio.tasks") == 1


class TestCeleryHelpers:
    @pytest.mark.parametrize(
        ("task_name", "expected"),
        [
            ("reindex_document", "reindex"),
            ("delete_document_background", "delete"),
            ("process_file_upload", "process"),
            ("generate_video_presentation", "generate"),
            ("podcast.draft_transcript", "podcast.draft"),
            ("podcast.render_audio", "podcast.render"),
            ("check_periodic_schedules", "check"),
            ("index_notion_pages", "index"),
            ("noseparator", "noseparator"),
            ("", "unknown"),
        ],
    )
    def test_parse_celery_task_label(self, task_name: str, expected: str) -> None:
        assert celery.parse_celery_task_label(task_name) == expected

    def test_parse_celery_task_label_handles_none(self) -> None:
        assert celery.parse_celery_task_label(None) == "unknown"

    def test_record_celery_queue_latency_noops_when_disabled(self) -> None:
        celery.record_celery_queue_latency(
            0.5,
            task_name="index_notion_pages",
            queue="surfsense.connectors",
            scheduled=False,
            operation="index",
        )
