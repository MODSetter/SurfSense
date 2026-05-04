"""Server-side mirror of the frontend's assistant-ui ``ContentPart`` projection.

Background
----------
The streaming chat task in ``stream_new_chat`` / ``stream_resume_chat`` yields
SSE events that the frontend folds into a ``ContentPartsState`` (see
``surfsense_web/lib/chat/streaming-state.ts`` and the matching pipeline in
``stream-pipeline.ts``). When a turn ends, the frontend calls
``buildContentForPersistence(...)`` and round-trips that ``ContentPart[]``
JSONB to ``POST /threads/{id}/messages``, which is what was historically
written to ``new_chat_messages.content``.

After the ghost-thread fix moved persistence server-side, the assistant
row is written by ``finalize_assistant_turn`` in the streaming finally
block. The frontend's later ``appendMessage`` is now a no-op (recovers
via the ``(thread_id, turn_id, role)`` partial unique index added in
migration 141), which means the *server* is now responsible for
producing the rich ``ContentPart[]`` shape the FE expects on history
reload — text + reasoning + tool-call cards (with ``args``, ``argsText``,
``result``, ``langchainToolCallId``) + thinking-step buckets +
step-separators.

This module is the in-memory accumulator that mirrors the FE state for
exactly that purpose. The streaming code calls ``on_text_*`` / ``on_reasoning_*``
/ ``on_tool_*`` / ``on_thinking_step`` / ``on_step_separator`` /
``mark_interrupted`` at the same call sites it yields the matching
``streaming_service.format_*`` SSE event, so the in-memory ``parts`` list
stays in lockstep with what the FE's pipeline would have produced live.
``snapshot()`` is then taken once in the ``finally`` block and persisted
in a single UPDATE.

Pure synchronous state — no DB I/O, no async, no flush callbacks. The
streaming code is responsible for driving lifecycle methods; this class
is a thin projection helper.
"""

from __future__ import annotations

import copy
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


# Mirrors the FE's filter in ``buildContentForPersistence`` / ``buildContentForUI``:
# only text/reasoning/tool-call parts count as "meaningful". data-thinking-steps
# and data-step-separator decorate the meaningful parts but never stand alone
# in a successful turn.
_MEANINGFUL_PART_TYPES: frozenset[str] = frozenset({"text", "reasoning", "tool-call"})


class AssistantContentBuilder:
    """Server-side projection of ``surfsense_web/lib/chat/streaming-state.ts``.

    Output shape (deep copy of ``self.parts`` via ``snapshot()``) strictly
    matches the FE ``ContentPart`` union::

        | { type: "text"; text: string }
        | { type: "reasoning"; text: string }
        | { type: "tool-call"; toolCallId: str; toolName: str;
            args: dict; result?: any; argsText?: str; langchainToolCallId?: str;
            state?: "aborted" }
        | { type: "data-thinking-steps"; data: { steps: ThinkingStepData[] } }
        | { type: "data-step-separator"; data: { stepIndex: int } }

    Order matches the wire order of the SSE events that drive the lifecycle
    methods, with two FE-mirrored exceptions:

    1. ``data-thinking-steps`` is a *singleton* and pinned at index 0 the
       first time we see a ``data-thinking-step`` SSE event (the FE's
       ``updateThinkingSteps`` does ``unshift`` on first sight). Subsequent
       thinking-step updates mutate that singleton in place.
    2. ``data-step-separator`` is appended only when the message already has
       meaningful content and the previous part isn't itself a separator
       (so the FIRST step of a turn doesn't generate a leading divider).
    """

    def __init__(self) -> None:
        self.parts: list[dict[str, Any]] = []
        # Index of the active text/reasoning part within ``parts`` while
        # streaming is open; -1 means "no active part" and the next delta
        # opens a fresh one. Mirrors ``ContentPartsState.currentTextPartIndex``.
        self._current_text_idx: int = -1
        self._current_reasoning_idx: int = -1
        # ``ui_id``-keyed indexes for tool-call parts. ``ui_id`` is the
        # synthetic ``call_<run_id>`` (legacy) or the LangChain
        # ``tool_call.id`` (parity_v2) — same key the streaming layer
        # threads through every ``tool-input-*`` / ``tool-output-*`` event.
        self._tool_call_idx_by_ui_id: dict[str, int] = {}
        # Live argsText accumulator (concatenated ``tool-input-delta`` chunks)
        # so we can reproduce the FE's ``appendToolInputDelta`` behaviour
        # before ``tool-input-available`` overwrites it with the
        # pretty-printed final JSON.
        self._args_text_by_ui_id: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Text
    # ------------------------------------------------------------------

    def on_text_start(self, text_id: str) -> None:
        """Begin a fresh text block.

        Symmetric to FE ``appendText``: opening text closes any active
        reasoning so the renderer treats them as separate parts. The
        actual text part isn't materialised here — it's lazily created
        on the first ``on_text_delta`` so an empty start/end pair
        leaves no trace. Matches the FE pipeline which has no explicit
        ``text-start`` handler at all.
        """
        if self._current_reasoning_idx >= 0:
            self._current_reasoning_idx = -1

    def on_text_delta(self, text_id: str, delta: str) -> None:
        if not delta:
            return
        if self._current_reasoning_idx >= 0:
            # FE behaviour: a text delta after reasoning implicitly
            # closes the reasoning block (see ``appendText`` lines
            # 178-180).
            self._current_reasoning_idx = -1
        if (
            self._current_text_idx >= 0
            and 0 <= self._current_text_idx < len(self.parts)
            and self.parts[self._current_text_idx].get("type") == "text"
        ):
            self.parts[self._current_text_idx]["text"] += delta
            return
        self.parts.append({"type": "text", "text": delta})
        self._current_text_idx = len(self.parts) - 1

    def on_text_end(self, text_id: str) -> None:
        """Close the active text block.

        Mirrors the wire-level ``text-end`` boundary the streaming layer
        emits before tool calls / reasoning / step boundaries. The FE
        pipeline implicitly closes via ``currentTextPartIndex = -1``
        in ``addToolCall`` / ``appendReasoning`` / ``addStepSeparator``;
        our helper does the same explicitly so callers don't have to
        maintain that invariant per call site.
        """
        self._current_text_idx = -1

    # ------------------------------------------------------------------
    # Reasoning
    # ------------------------------------------------------------------

    def on_reasoning_start(self, reasoning_id: str) -> None:
        if self._current_text_idx >= 0:
            self._current_text_idx = -1

    def on_reasoning_delta(self, reasoning_id: str, delta: str) -> None:
        if not delta:
            return
        if self._current_text_idx >= 0:
            self._current_text_idx = -1
        if (
            self._current_reasoning_idx >= 0
            and 0 <= self._current_reasoning_idx < len(self.parts)
            and self.parts[self._current_reasoning_idx].get("type") == "reasoning"
        ):
            self.parts[self._current_reasoning_idx]["text"] += delta
            return
        self.parts.append({"type": "reasoning", "text": delta})
        self._current_reasoning_idx = len(self.parts) - 1

    def on_reasoning_end(self, reasoning_id: str) -> None:
        self._current_reasoning_idx = -1

    # ------------------------------------------------------------------
    # Tool calls
    # ------------------------------------------------------------------

    def on_tool_input_start(
        self,
        ui_id: str,
        tool_name: str,
        langchain_tool_call_id: str | None,
    ) -> None:
        """Register a tool-call card. Args are filled in by later events."""
        if not ui_id:
            return
        # Skip duplicate registration: parity_v2 may emit
        # ``tool-input-start`` from both ``on_chat_model_stream``
        # (when tool_call_chunks register a name) and ``on_tool_start``
        # (the canonical path). The FE de-dupes via ``toolCallIndices``;
        # we mirror that here.
        if ui_id in self._tool_call_idx_by_ui_id:
            if langchain_tool_call_id:
                idx = self._tool_call_idx_by_ui_id[ui_id]
                part = self.parts[idx]
                if not part.get("langchainToolCallId"):
                    part["langchainToolCallId"] = langchain_tool_call_id
            return

        part: dict[str, Any] = {
            "type": "tool-call",
            "toolCallId": ui_id,
            "toolName": tool_name,
            "args": {},
        }
        if langchain_tool_call_id:
            part["langchainToolCallId"] = langchain_tool_call_id
        self.parts.append(part)
        self._tool_call_idx_by_ui_id[ui_id] = len(self.parts) - 1

        self._current_text_idx = -1
        self._current_reasoning_idx = -1

    def on_tool_input_delta(self, ui_id: str, args_chunk: str) -> None:
        """Append a streamed args-delta chunk to the matching card's argsText.

        Mirrors FE ``appendToolInputDelta``: no-ops when no card has been
        registered yet for the given ``ui_id`` — the deltas have nowhere
        safe to land.
        """
        if not ui_id or not args_chunk:
            return
        idx = self._tool_call_idx_by_ui_id.get(ui_id)
        if idx is None:
            return
        if not (0 <= idx < len(self.parts)):
            return
        part = self.parts[idx]
        if part.get("type") != "tool-call":
            return
        new_text = (part.get("argsText") or "") + args_chunk
        part["argsText"] = new_text
        self._args_text_by_ui_id[ui_id] = new_text

    def on_tool_input_available(
        self,
        ui_id: str,
        tool_name: str,
        args: dict[str, Any],
        langchain_tool_call_id: str | None,
    ) -> None:
        """Finalize the tool-call card's input.

        Mirrors FE ``stream-pipeline.ts`` lines 127-153: replaces ``argsText``
        with ``json.dumps(input, indent=2)`` so the post-stream card renders
        pretty-printed JSON, sets the full ``args`` dict, and backfills
        ``langchainToolCallId`` if it wasn't known at ``tool-input-start`` time.
        Also creates the card if no prior ``tool-input-start`` registered it
        (legacy parity_v2-OFF / late-registration paths).
        """
        if not ui_id:
            return
        try:
            final_args_text = json.dumps(args or {}, indent=2, ensure_ascii=False)
        except (TypeError, ValueError):
            # Defensive: ``args`` should already be JSON-safe (the
            # streaming layer sanitizes it before emitting), but if a
            # caller hands us a non-serializable value we still want
            # to record the call without breaking the snapshot.
            final_args_text = str(args)

        idx = self._tool_call_idx_by_ui_id.get(ui_id)
        if idx is not None and 0 <= idx < len(self.parts):
            part = self.parts[idx]
            if part.get("type") == "tool-call":
                part["args"] = args or {}
                part["argsText"] = final_args_text
                if langchain_tool_call_id and not part.get("langchainToolCallId"):
                    part["langchainToolCallId"] = langchain_tool_call_id
                return

        # No prior tool-input-start: register the card now.
        new_part: dict[str, Any] = {
            "type": "tool-call",
            "toolCallId": ui_id,
            "toolName": tool_name,
            "args": args or {},
            "argsText": final_args_text,
        }
        if langchain_tool_call_id:
            new_part["langchainToolCallId"] = langchain_tool_call_id
        self.parts.append(new_part)
        self._tool_call_idx_by_ui_id[ui_id] = len(self.parts) - 1

        self._current_text_idx = -1
        self._current_reasoning_idx = -1

    def on_tool_output_available(
        self,
        ui_id: str,
        output: Any,
        langchain_tool_call_id: str | None,
    ) -> None:
        """Attach the tool's output (``result``) to the matching card.

        Mirrors FE ``updateToolCall``: backfill ``langchainToolCallId``
        only if not already set (a NULL late-arriving value never blows
        away an earlier known good one).
        """
        if not ui_id:
            return
        idx = self._tool_call_idx_by_ui_id.get(ui_id)
        if idx is None or not (0 <= idx < len(self.parts)):
            return
        part = self.parts[idx]
        if part.get("type") != "tool-call":
            return
        part["result"] = output
        if langchain_tool_call_id and not part.get("langchainToolCallId"):
            part["langchainToolCallId"] = langchain_tool_call_id

    # ------------------------------------------------------------------
    # Thinking steps & step separators
    # ------------------------------------------------------------------

    def on_thinking_step(
        self,
        step_id: str,
        title: str,
        status: str,
        items: list[str] | None,
    ) -> None:
        """Update / insert the singleton ``data-thinking-steps`` part.

        Mirrors FE ``updateThinkingSteps``: maintain a single
        ``data-thinking-steps`` part anchored at index 0, replacing or
        unshifting on first sight. Each ``on_thinking_step`` call
        replaces the entry in the steps list keyed by ``step_id`` (or
        appends if new).
        """
        if not step_id:
            return

        new_step = {
            "id": step_id,
            "title": title or "",
            "status": status or "in_progress",
            "items": list(items) if items else [],
        }

        # Find existing data-thinking-steps part.
        existing_idx = -1
        for i, p in enumerate(self.parts):
            if p.get("type") == "data-thinking-steps":
                existing_idx = i
                break

        if existing_idx >= 0:
            current_steps = self.parts[existing_idx].get("data", {}).get("steps") or []
            replaced = False
            for i, step in enumerate(current_steps):
                if step.get("id") == step_id:
                    current_steps[i] = new_step
                    replaced = True
                    break
            if not replaced:
                current_steps.append(new_step)
            self.parts[existing_idx] = {
                "type": "data-thinking-steps",
                "data": {"steps": current_steps},
            }
            return

        # First sight: unshift to position 0 (FE parity).
        self.parts.insert(
            0,
            {
                "type": "data-thinking-steps",
                "data": {"steps": [new_step]},
            },
        )
        # Bump tracked indices since we inserted at the head.
        if self._current_text_idx >= 0:
            self._current_text_idx += 1
        if self._current_reasoning_idx >= 0:
            self._current_reasoning_idx += 1
        for ui_id, idx in list(self._tool_call_idx_by_ui_id.items()):
            self._tool_call_idx_by_ui_id[ui_id] = idx + 1

    def on_step_separator(self) -> None:
        """Append a ``data-step-separator`` between consecutive model steps.

        Mirrors FE ``addStepSeparator``: only emit when the message
        already has meaningful content AND the previous part isn't
        itself a separator. ``stepIndex`` is the running count of
        separators already in ``parts``.
        """
        has_content = any(p.get("type") in _MEANINGFUL_PART_TYPES for p in self.parts)
        if not has_content:
            return
        if self.parts and self.parts[-1].get("type") == "data-step-separator":
            return
        step_index = sum(
            1 for p in self.parts if p.get("type") == "data-step-separator"
        )
        self.parts.append(
            {
                "type": "data-step-separator",
                "data": {"stepIndex": step_index},
            }
        )
        self._current_text_idx = -1
        self._current_reasoning_idx = -1

    # ------------------------------------------------------------------
    # Interruption handling
    # ------------------------------------------------------------------

    def mark_interrupted(self) -> None:
        """Close any open text/reasoning and flip running tools to aborted.

        Called from the streaming ``finally`` block before ``snapshot()`` so
        the persisted JSONB reflects a coherent end-state even when the
        client disconnected mid-turn or the agent hit a fatal error.

        - Active text/reasoning blocks: simply lose their "active"
          marker (no synthetic content appended). Whatever was streamed
          stays as-is.
        - Tool-call parts that never received a ``result`` get
          ``state="aborted"`` so the FE history loader can render them
          as "interrupted" rather than "still running".
        """
        self._current_text_idx = -1
        self._current_reasoning_idx = -1
        for part in self.parts:
            if part.get("type") != "tool-call":
                continue
            if "result" in part:
                continue
            part["state"] = "aborted"

    # ------------------------------------------------------------------
    # Snapshot & introspection
    # ------------------------------------------------------------------

    def snapshot(self) -> list[dict[str, Any]]:
        """Return a deep copy of ``parts`` ready for SQL UPDATE / json.dumps.

        Deep-copied so callers that finalize from the shielded ``finally``
        block can't accidentally mutate the persisted payload while the
        SQL UPDATE is in flight (the streaming layer doesn't touch the
        builder after this call, but defensive copies are cheap and cheap
        is what we want in a finally block).
        """
        return copy.deepcopy(self.parts)

    def is_empty(self) -> bool:
        """True if no meaningful content was captured.

        ``data-thinking-steps`` and ``data-step-separator`` decorate
        meaningful content but don't count on their own — a turn that
        only emitted a thinking step before being interrupted should
        still be treated as empty for the status-marker fallback.
        """
        return not any(p.get("type") in _MEANINGFUL_PART_TYPES for p in self.parts)

    def stats(self) -> dict[str, int]:
        """Return counts of each part-type plus rough byte size.

        Used by the streaming layer's perf logger so an ops dashboard
        can correlate finalize latency with payload size, and so a
        regression that quietly stops emitting tool-call parts (or
        starts emitting hundreds) shows up in [PERF] grep rather than
        only as a "history reload looks weird" bug report.

        ``bytes`` is the JSON-serialised payload length — what actually
        crosses the wire to PostgreSQL's JSONB column. We compute it
        with ``ensure_ascii=False`` to match the JSONB encoder's UTF-8
        on-disk layout closely enough for back-of-the-envelope sizing.
        Reasoning/text/tool-call/thinking-step/step-separator counts are
        independent so any one can spike without the others.

        Defensive: ``json.dumps`` failure (a non-serializable value
        slipped past the streaming layer's sanitization) is reported as
        ``bytes=-1`` rather than raised — perf logging must not be the
        thing that breaks the streaming finally block.
        """
        text_blocks = 0
        reasoning_blocks = 0
        tool_calls = 0
        tool_calls_completed = 0
        tool_calls_aborted = 0
        thinking_step_parts = 0
        step_separators = 0

        for part in self.parts:
            kind = part.get("type")
            if kind == "text":
                text_blocks += 1
            elif kind == "reasoning":
                reasoning_blocks += 1
            elif kind == "tool-call":
                tool_calls += 1
                if part.get("state") == "aborted":
                    tool_calls_aborted += 1
                elif "result" in part:
                    tool_calls_completed += 1
            elif kind == "data-thinking-steps":
                thinking_step_parts += 1
            elif kind == "data-step-separator":
                step_separators += 1

        try:
            byte_size = len(json.dumps(self.parts, ensure_ascii=False, default=str))
        except (TypeError, ValueError):
            byte_size = -1

        return {
            "parts": len(self.parts),
            "bytes": byte_size,
            "text": text_blocks,
            "reasoning": reasoning_blocks,
            "tool_calls": tool_calls,
            "tool_calls_completed": tool_calls_completed,
            "tool_calls_aborted": tool_calls_aborted,
            "thinking_step_parts": thinking_step_parts,
            "step_separators": step_separators,
        }
