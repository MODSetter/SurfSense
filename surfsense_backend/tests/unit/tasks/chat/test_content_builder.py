"""Unit tests for ``AssistantContentBuilder``.

Pins the in-memory ``ContentPart[]`` projection so the JSONB the server
persists matches what the frontend renders live (see
``surfsense_web/lib/chat/streaming-state.ts``). Every test asserts both
the structural shape of ``snapshot()`` and that the snapshot is
``json.dumps``-safe (the streaming finally block writes it directly to
``new_chat_messages.content`` without an explicit serialization round
trip).
"""

from __future__ import annotations

import json

import pytest

from app.services.new_streaming_service import VercelStreamingService
from app.tasks.chat.content_builder import AssistantContentBuilder

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _assert_jsonb_safe(parts: list[dict]) -> None:
    """Sanity check: any snapshot must round-trip through ``json.dumps``."""
    serialized = json.dumps(parts)
    assert json.loads(serialized) == parts


# ---------------------------------------------------------------------------
# Text turns
# ---------------------------------------------------------------------------


class TestTextOnly:
    def test_single_text_block_collapses_consecutive_deltas(self):
        b = AssistantContentBuilder()
        b.on_text_start("text-1")
        b.on_text_delta("text-1", "Hello")
        b.on_text_delta("text-1", " ")
        b.on_text_delta("text-1", "world")
        b.on_text_end("text-1")

        snap = b.snapshot()
        assert snap == [{"type": "text", "text": "Hello world"}]
        assert not b.is_empty()
        _assert_jsonb_safe(snap)

    def test_empty_text_start_end_pair_leaves_no_part(self):
        # Mirrors the FE: a text-start without any deltas should
        # not materialise an empty ``{"type":"text","text":""}`` part.
        b = AssistantContentBuilder()
        b.on_text_start("text-1")
        b.on_text_end("text-1")

        assert b.snapshot() == []
        assert b.is_empty()

    def test_text_after_text_end_starts_fresh_part(self):
        b = AssistantContentBuilder()
        b.on_text_start("text-1")
        b.on_text_delta("text-1", "first")
        b.on_text_end("text-1")

        b.on_text_start("text-2")
        b.on_text_delta("text-2", "second")
        b.on_text_end("text-2")

        snap = b.snapshot()
        assert snap == [
            {"type": "text", "text": "first"},
            {"type": "text", "text": "second"},
        ]


class TestReasoningThenText:
    def test_reasoning_followed_by_text_yields_two_parts_in_order(self):
        b = AssistantContentBuilder()
        b.on_reasoning_start("r-1")
        b.on_reasoning_delta("r-1", "Considering options...")
        b.on_reasoning_end("r-1")

        b.on_text_start("text-1")
        b.on_text_delta("text-1", "The answer is 42.")
        b.on_text_end("text-1")

        snap = b.snapshot()
        assert snap[0]["type"] == "reasoning"
        assert snap[0]["text"] == "Considering options..."
        assert snap[0]["id"] == "r-1"
        assert snap[0]["status"] == "completed"
        assert snap[0]["startedAt"]
        assert snap[0]["completedAt"]
        assert snap[1] == {"type": "text", "text": "The answer is 42."}
        _assert_jsonb_safe(snap)

    def test_text_delta_after_reasoning_implicitly_closes_reasoning(self):
        # Mirrors FE ``appendText``: a text delta arriving while a
        # reasoning part is "active" still produces a fresh text
        # part, never appends into the reasoning block.
        b = AssistantContentBuilder()
        b.on_reasoning_start("r-1")
        b.on_reasoning_delta("r-1", "thinking")
        # No explicit reasoning_end — text delta should close it.
        b.on_text_delta("text-1", "answer")

        snap = b.snapshot()
        assert snap[0]["type"] == "reasoning"
        assert snap[0]["text"] == "thinking"
        assert snap[0]["status"] == "running"
        assert snap[1] == {"type": "text", "text": "answer"}


# ---------------------------------------------------------------------------
# Tool calls
# ---------------------------------------------------------------------------


class TestToolHeavyTurn:
    def test_full_tool_lifecycle_produces_complete_tool_call_part(self):
        b = AssistantContentBuilder()
        # Some narration before the tool fires.
        b.on_text_start("text-1")
        b.on_text_delta("text-1", "Searching...")
        b.on_text_end("text-1")

        b.on_tool_input_start(
            ui_id="call_run123",
            tool_name="scrape_webpage",
            langchain_tool_call_id="lc_tool_abc",
        )
        b.on_tool_input_delta("call_run123", '{"query":')
        b.on_tool_input_delta("call_run123", '"surfsense"}')
        b.on_tool_input_available(
            ui_id="call_run123",
            tool_name="scrape_webpage",
            args={"query": "surfsense"},
            langchain_tool_call_id="lc_tool_abc",
        )
        b.on_tool_output_available(
            ui_id="call_run123",
            output={"status": "completed", "citations": {}},
            langchain_tool_call_id="lc_tool_abc",
        )

        snap = b.snapshot()
        assert snap[0] == {"type": "text", "text": "Searching..."}
        tool_part = snap[1]
        assert tool_part["type"] == "tool-call"
        assert tool_part["toolCallId"] == "call_run123"
        assert tool_part["toolName"] == "scrape_webpage"
        assert tool_part["args"] == {"query": "surfsense"}
        # ``argsText`` is the pretty-printed final JSON, not the raw
        # streaming buffer (FE ``stream-pipeline.ts:128``).
        assert tool_part["argsText"] == json.dumps(
            {"query": "surfsense"}, indent=2, ensure_ascii=False
        )
        assert tool_part["langchainToolCallId"] == "lc_tool_abc"
        assert tool_part["result"] == {"status": "completed", "citations": {}}
        _assert_jsonb_safe(snap)

    def test_tool_input_available_without_prior_start_creates_card(self):
        # Late-registration: tool-input-available may be
        # emitted without a prior tool-input-start (no streamed
        # tool_call_chunks). The card should still be created.
        b = AssistantContentBuilder()
        b.on_tool_input_available(
            ui_id="call_run42",
            tool_name="grep",
            args={"pattern": "TODO"},
            langchain_tool_call_id="lc_x",
        )
        b.on_tool_output_available(
            ui_id="call_run42",
            output={"matches": 3},
            langchain_tool_call_id="lc_x",
        )

        snap = b.snapshot()
        assert len(snap) == 1
        part = snap[0]
        assert part["type"] == "tool-call"
        assert part["toolCallId"] == "call_run42"
        assert part["args"] == {"pattern": "TODO"}
        assert part["langchainToolCallId"] == "lc_x"
        assert part["result"] == {"matches": 3}

    def test_tool_input_start_idempotent_for_same_ui_id(self):
        # tool-input-start can fire from BOTH the chunk
        # registration path AND the canonical ``on_tool_start`` path.
        # The second call must not create a duplicate part.
        b = AssistantContentBuilder()
        b.on_tool_input_start("call_x", "ls", "lc_x")
        b.on_tool_input_start("call_x", "ls", "lc_x")
        snap = b.snapshot()
        assert len(snap) == 1

    def test_tool_input_delta_without_prior_start_is_silently_dropped(self):
        b = AssistantContentBuilder()
        b.on_tool_input_delta("call_unknown", '{"orphan": "delta"}')
        assert b.snapshot() == []

    def test_langchain_tool_call_id_backfills_only_when_absent(self):
        b = AssistantContentBuilder()
        b.on_tool_input_start("call_x", "ls", "lc_first")
        # Late event must NOT clobber an already-set lc id.
        b.on_tool_input_start("call_x", "ls", "lc_late")
        snap = b.snapshot()
        assert snap[0]["langchainToolCallId"] == "lc_first"

    def test_args_text_streaming_buffer_reflects_concatenation(self):
        b = AssistantContentBuilder()
        b.on_tool_input_start("call_x", "save_doc", "lc_y")
        b.on_tool_input_delta("call_x", '{"title":')
        b.on_tool_input_delta("call_x", '"Hi"}')
        # Snapshot mid-stream should see the partial buffer (the FE
        # tolerates invalid JSON and renders it as-is).
        mid = b.snapshot()
        assert mid[0]["argsText"] == '{"title":"Hi"}'
        # Then tool-input-available replaces with pretty-printed.
        b.on_tool_input_available(
            "call_x",
            "save_doc",
            {"title": "Hi"},
            "lc_y",
        )
        final = b.snapshot()
        assert final[0]["argsText"] == json.dumps(
            {"title": "Hi"}, indent=2, ensure_ascii=False
        )


# ---------------------------------------------------------------------------
# Task-span metadata on tool-call parts (JSONB persistence)
# ---------------------------------------------------------------------------


class TestToolCallSpanMetadata:
    def test_input_available_merges_new_metadata_keys_after_start(self):
        b = AssistantContentBuilder()
        b.on_tool_input_start("call_t", "task", "lc_t", metadata={"spanId": "spn_1"})
        b.on_tool_input_available(
            "call_t",
            "task",
            {"goal": "x"},
            "lc_t",
            metadata={"traceId": "tr_1"},
        )
        part = b.snapshot()[0]
        assert part["metadata"]["spanId"] == "spn_1"
        assert part["metadata"]["traceId"] == "tr_1"
        _assert_jsonb_safe(b.snapshot())

    def test_input_available_does_not_overwrite_existing_metadata_keys(self):
        b = AssistantContentBuilder()
        b.on_tool_input_start("call_t", "task", "lc_t", metadata={"spanId": "spn_keep"})
        b.on_tool_input_available(
            "call_t", "task", {}, "lc_t", metadata={"spanId": "spn_other"}
        )
        assert b.snapshot()[0]["metadata"]["spanId"] == "spn_keep"

    def test_late_tool_input_available_carries_metadata(self):
        b = AssistantContentBuilder()
        b.on_tool_input_available(
            "call_l",
            "grep",
            {"pattern": "TODO"},
            None,
            metadata={"spanId": "spn_l"},
        )
        part = b.snapshot()[0]
        assert part["metadata"] == {"spanId": "spn_l"}
        _assert_jsonb_safe(b.snapshot())

    def test_output_available_merges_without_clobbering_span_id(self):
        b = AssistantContentBuilder()
        b.on_tool_input_start("call_t", "ls", "lc", metadata={"spanId": "spn_x"})
        b.on_tool_input_available("call_t", "ls", {"path": "/"}, "lc")
        b.on_tool_output_available(
            "call_t",
            {"ok": True},
            "lc",
            metadata={"spanId": "spn_y", "extra": 1},
        )
        md = b.snapshot()[0]["metadata"]
        assert md["spanId"] == "spn_x"
        assert md["extra"] == 1

    def test_output_available_preserves_activity_id_without_clobbering_span(self):
        b = AssistantContentBuilder()
        b.on_tool_input_start(
            "call_t",
            "ls",
            "lc",
            metadata={"spanId": "spn_x", "activityId": "act_turn_3"},
        )
        b.on_tool_input_available("call_t", "ls", {"path": "/"}, "lc")
        b.on_tool_output_available(
            "call_t",
            {"ok": True},
            "lc",
            metadata={"spanId": "spn_x", "activityId": "act_turn_3"},
        )
        md = b.snapshot()[0]["metadata"]
        assert md["spanId"] == "spn_x"
        assert md["activityId"] == "act_turn_3"

    def test_output_available_with_none_metadata_preserves_prior(self):
        b = AssistantContentBuilder()
        b.on_tool_input_start("c", "ls", "lc", metadata={"spanId": "spn_1"})
        b.on_tool_input_available("c", "ls", {}, "lc")
        b.on_tool_output_available("c", {"r": 1}, "lc", metadata=None)
        assert b.snapshot()[0]["metadata"] == {"spanId": "spn_1"}

    def test_available_adds_activity_id_after_chunk_only_start(self):
        """Mirrors chunk ``tool-input-start`` then ``on_tool_start`` ``available``."""
        b = AssistantContentBuilder()
        b.on_tool_input_start("lc_1", "ls", "lc_1", metadata={"spanId": "spn_a"})
        b.on_tool_input_available(
            "lc_1",
            "ls",
            {"path": "/"},
            "lc_1",
            metadata={"spanId": "spn_a", "activityId": "act_turn_2"},
        )
        md = b.snapshot()[0]["metadata"]
        assert md["spanId"] == "spn_a"
        assert md["activityId"] == "act_turn_2"


class TestVercelStreamingServiceToolMetadataWire:
    """SSE payloads include optional ``metadata`` for FE grouping."""

    @staticmethod
    def _parse_sse_data_line(raw: str) -> dict:
        assert raw.startswith("data: ")
        payload = raw.split("data: ", 1)[1].split("\n\n", 1)[0].strip()
        return json.loads(payload)

    def test_tool_input_available_includes_metadata_when_set(self):
        svc = VercelStreamingService()
        raw = svc.format_tool_input_available(
            "id1",
            "task",
            {"a": 1},
            langchain_tool_call_id="lc1",
            metadata={"spanId": "spn_w", "activityId": "act_turn_4"},
        )
        body = self._parse_sse_data_line(raw)
        assert body["type"] == "tool-input-available"
        assert body["metadata"] == {
            "spanId": "spn_w",
            "activityId": "act_turn_4",
        }

    def test_tool_output_available_includes_metadata_when_set(self):
        svc = VercelStreamingService()
        raw = svc.format_tool_output_available(
            "id1",
            {"status": "completed"},
            langchain_tool_call_id="lc1",
            metadata={"spanId": "spn_o", "activityId": "act_turn_9"},
        )
        body = self._parse_sse_data_line(raw)
        assert body["type"] == "tool-output-available"
        assert body["metadata"] == {
            "spanId": "spn_o",
            "activityId": "act_turn_9",
        }

    def test_tool_input_available_omits_metadata_key_when_none(self):
        svc = VercelStreamingService()
        raw = svc.format_tool_input_available("id1", "ls", {})
        body = self._parse_sse_data_line(raw)
        assert "metadata" not in body


# ---------------------------------------------------------------------------
# Activities & separators
# ---------------------------------------------------------------------------


def _activity(
    activity_id: str,
    sequence: int,
    *,
    status: str = "running",
    title: str = "Working",
) -> dict:
    return {
        "id": activity_id,
        "sequence": sequence,
        "kind": "action",
        "status": status,
        "title": title,
        "category": "action",
        "iconKey": "action",
        "startedAt": "2026-01-01T00:00:00+00:00",
    }


class TestActivities:
    def test_first_activity_unshifts_singleton_to_index_zero(self):
        b = AssistantContentBuilder()
        b.on_text_start("text-1")
        b.on_text_delta("text-1", "Hello")
        b.on_text_end("text-1")

        b.on_activity(_activity("act-1", 1))

        snap = b.snapshot()
        assert snap[0]["type"] == "data-activities"
        assert snap[0]["data"]["activities"] == [_activity("act-1", 1)]
        assert snap[1] == {"type": "text", "text": "Hello"}

    def test_snapshots_upsert_by_id_and_sort_by_sequence(self):
        b = AssistantContentBuilder()
        b.on_activity(_activity("act-2", 2))
        b.on_activity(_activity("act-1", 1))
        b.on_activity(_activity("act-1", 1, status="completed", title="Done"))

        snap = b.snapshot()
        assert len([p for p in snap if p["type"] == "data-activities"]) == 1
        activities = snap[0]["data"]["activities"]
        assert [activity["id"] for activity in activities] == ["act-1", "act-2"]
        assert activities[0]["status"] == "completed"

    def test_terminal_activity_cannot_regress(self):
        b = AssistantContentBuilder()
        b.on_activity(_activity("act-1", 1, status="completed", title="Done"))
        b.on_activity(_activity("act-1", 1))
        assert b.snapshot()[0]["data"]["activities"][0]["status"] == "completed"

    def test_activity_without_id_is_dropped(self):
        b = AssistantContentBuilder()
        b.on_activity({})
        assert b.snapshot() == []
        assert b.is_empty()


# ---------------------------------------------------------------------------
# Interruption handling
# ---------------------------------------------------------------------------


class TestMarkInterrupted:
    def test_running_activities_interrupt_but_approval_pauses_are_preserved(self):
        b = AssistantContentBuilder()
        b.on_activity(_activity("running", 1))
        b.on_activity(_activity("approval", 2, status="awaiting_approval"))

        b.mark_interrupted()

        activities = b.snapshot()[0]["data"]["activities"]
        assert activities[0]["status"] == "interrupted"
        assert activities[0]["completedAt"]
        assert activities[1]["status"] == "awaiting_approval"
        assert "completedAt" not in activities[1]

    def test_running_tool_calls_get_state_aborted(self):
        b = AssistantContentBuilder()
        b.on_tool_input_start("call_a", "ls", "lc_a")
        b.on_tool_input_available("call_a", "ls", {"path": "/"}, "lc_a")
        # No tool-output-available — simulates client disconnect mid-tool.

        b.mark_interrupted()

        snap = b.snapshot()
        assert snap[0]["state"] == "aborted"
        assert "result" not in snap[0]

    def test_completed_tool_calls_are_not_marked_aborted(self):
        b = AssistantContentBuilder()
        b.on_tool_input_start("call_a", "ls", "lc_a")
        b.on_tool_input_available("call_a", "ls", {"path": "/"}, "lc_a")
        b.on_tool_output_available("call_a", {"files": []}, "lc_a")

        b.mark_interrupted()

        snap = b.snapshot()
        assert "state" not in snap[0]
        assert snap[0]["result"] == {"files": []}

    def test_open_text_block_keeps_accumulated_content(self):
        b = AssistantContentBuilder()
        b.on_text_start("text-1")
        b.on_text_delta("text-1", "partial")
        # No on_text_end — disconnect mid-stream.

        b.mark_interrupted()

        snap = b.snapshot()
        assert snap == [{"type": "text", "text": "partial"}]


# ---------------------------------------------------------------------------
# is_empty / snapshot semantics
# ---------------------------------------------------------------------------


class TestIsEmpty:
    def test_fresh_builder_is_empty(self):
        assert AssistantContentBuilder().is_empty()

    def test_text_part_breaks_emptiness(self):
        b = AssistantContentBuilder()
        b.on_text_delta("text-1", "x")
        assert not b.is_empty()

    def test_tool_call_breaks_emptiness(self):
        b = AssistantContentBuilder()
        b.on_tool_input_start("call_x", "ls", None)
        assert not b.is_empty()

    def test_activity_alone_does_not_break_emptiness(self):
        b = AssistantContentBuilder()
        b.on_activity(_activity("act-1", 1))
        assert b.is_empty()

class TestSnapshotSemantics:
    def test_snapshot_is_deep_copied_so_mutations_do_not_leak(self):
        b = AssistantContentBuilder()
        b.on_tool_input_start("call_x", "ls", "lc_x")
        b.on_tool_input_available("call_x", "ls", {"path": "/"}, "lc_x")
        snap = b.snapshot()
        # Mutate the returned snapshot — original should be untouched.
        snap[0]["args"]["mutated"] = True
        snap[0]["state"] = "tampered"

        again = b.snapshot()
        assert "mutated" not in again[0]["args"]
        assert "state" not in again[0]

    def test_snapshot_round_trips_through_json(self):
        b = AssistantContentBuilder()
        b.on_activity(_activity("act-1", 1))
        b.on_text_delta("text-1", "answer")
        b.on_tool_input_start("call_x", "ls", "lc_x")
        b.on_tool_input_available("call_x", "ls", {"path": "/"}, "lc_x")
        b.on_tool_output_available("call_x", {"files": ["a.txt"]}, "lc_x")
        snap = b.snapshot()

        encoded = json.dumps(snap)
        assert json.loads(encoded) == snap


class TestStats:
    """``stats()`` is the perf-log handle for [PERF] [stream_*]
    finalize_payload lines. Pin the schema so an ops dashboard can
    rely on these keys being present and meaningful.
    """

    def test_fresh_builder_reports_all_zeros(self):
        b = AssistantContentBuilder()
        s = b.stats()
        assert s == {
            "parts": 0,
            "bytes": 2,  # ``[]`` is two bytes
            "text": 0,
            "reasoning": 0,
            "tool_calls": 0,
            "tool_calls_completed": 0,
            "tool_calls_aborted": 0,
            "activity_parts": 0,
        }

    def test_counts_each_part_type_independently(self):
        b = AssistantContentBuilder()
        b.on_text_start("t1")
        b.on_text_delta("t1", "hi")
        b.on_text_end("t1")
        b.on_reasoning_start("r1")
        b.on_reasoning_delta("r1", "thinking")
        b.on_reasoning_end("r1")
        b.on_activity(_activity("act-1", 1, status="completed", title="Done"))
        b.on_tool_input_start("call_done", "ls", "lc_done")
        b.on_tool_input_available("call_done", "ls", {}, "lc_done")
        b.on_tool_output_available("call_done", {"ok": True}, "lc_done")
        b.on_tool_input_start("call_running", "rm", "lc_running")
        b.on_tool_input_available("call_running", "rm", {}, "lc_running")

        s = b.stats()
        assert s["text"] == 1
        assert s["reasoning"] == 1
        assert s["tool_calls"] == 2
        assert s["tool_calls_completed"] == 1
        assert s["tool_calls_aborted"] == 0
        assert s["activity_parts"] == 1
        assert s["parts"] == sum(
            [
                s["text"],
                s["reasoning"],
                s["tool_calls"],
                s["activity_parts"],
            ]
        )
        assert s["bytes"] > 0

    def test_mark_interrupted_flips_running_calls_to_aborted_in_stats(self):
        b = AssistantContentBuilder()
        b.on_tool_input_start("call_done", "ls", "lc_done")
        b.on_tool_input_available("call_done", "ls", {}, "lc_done")
        b.on_tool_output_available("call_done", {"ok": True}, "lc_done")
        b.on_tool_input_start("call_running", "rm", "lc_running")
        b.on_tool_input_available("call_running", "rm", {}, "lc_running")

        # Pre-interrupt: one completed, one still running (no result).
        pre = b.stats()
        assert pre["tool_calls_completed"] == 1
        assert pre["tool_calls_aborted"] == 0

        b.mark_interrupted()
        post = b.stats()
        assert post["tool_calls_completed"] == 1
        assert post["tool_calls_aborted"] == 1
        assert post["tool_calls"] == 2

    def test_bytes_reflects_jsonb_payload_size(self):
        # Each text-delta adds bytes monotonically — useful for catching
        # an unbounded delta buffer regression in the perf signal.
        b = AssistantContentBuilder()
        b.on_text_start("t1")
        b.on_text_delta("t1", "x" * 10)
        small = b.stats()["bytes"]
        b.on_text_delta("t1", "x" * 1000)
        large = b.stats()["bytes"]
        assert large > small + 900
