import type { ThreadMessageLike } from "@assistant-ui/react";

export interface ThinkingStepData {
	id: string;
	title: string;
	status: "pending" | "in_progress" | "completed";
	items: string[];
}

export type ContentPart =
	| { type: "text"; text: string }
	| { type: "reasoning"; text: string }
	| {
			type: "tool-call";
			toolCallId: string;
			toolName: string;
			args: Record<string, unknown>;
			result?: unknown;
			/**
			 * Live / finalized JSON text for the tool's input arguments.
			 *
			 * - During streaming: accumulated partial JSON text from
			 *   ``tool-input-delta`` events (may be invalid JSON
			 *   mid-stream). assistant-ui's argsText parser tolerates
			 *   invalid JSON gracefully (changelog 0.7.32 / 0.7.78).
			 * - On completion (``tool-input-available``): replaced with
			 *   ``JSON.stringify(input, null, 2)`` so the post-stream
			 *   card renders pretty-printed JSON instead of the
			 *   model's possibly-fragmented formatting.
			 *
			 * Per assistant-ui ``ThreadMessageLike`` precedence
			 * (changelog 0.11.6 ``d318c83``), when ``argsText`` is
			 * supplied it wins over ``JSON.stringify(args)``.
			 */
			argsText?: string;
			/**
			 * Authoritative LangChain ``tool_call.id`` propagated by the backend
			 * via ``langchainToolCallId`` on tool-input-start/available and
			 * tool-output-available events. Used to join a card to the
			 * matching ``AgentActionLog`` row exposed by
			 * ``GET /threads/{id}/actions`` and the streamed
			 * ``data-action-log`` events.
			 */
			langchainToolCallId?: string;
	  }
	| {
			type: "data-thinking-steps";
			data: { steps: ThinkingStepData[] };
	  }
	| {
			/**
			 * Between-step separator. Pushed by `addStepSeparator` when
			 * a `start-step` SSE event arrives AFTER the message already
			 * has non-step content. Rendered by `StepSeparatorDataUI`
			 * (see assistant-ui/step-separator.tsx).
			 */
			type: "data-step-separator";
			data: { stepIndex: number };
	  };

export interface ContentPartsState {
	contentParts: ContentPart[];
	currentTextPartIndex: number;
	currentReasoningPartIndex: number;
	toolCallIndices: Map<string, number>;
}

function areThinkingStepsEqual(current: ThinkingStepData[], next: ThinkingStepData[]): boolean {
	if (current.length !== next.length) return false;

	for (let i = 0; i < current.length; i += 1) {
		const curr = current[i];
		const nxt = next[i];
		if (curr.id !== nxt.id || curr.title !== nxt.title || curr.status !== nxt.status) {
			return false;
		}
		if (curr.items.length !== nxt.items.length) return false;
		for (let j = 0; j < curr.items.length; j += 1) {
			if (curr.items[j] !== nxt.items[j]) return false;
		}
	}

	return true;
}

export function updateThinkingSteps(
	state: ContentPartsState,
	steps: Map<string, ThinkingStepData>
): boolean {
	const stepsArray = Array.from(steps.values());
	const existingIdx = state.contentParts.findIndex((p) => p.type === "data-thinking-steps");

	if (existingIdx >= 0) {
		const existing = state.contentParts[existingIdx];
		if (
			existing?.type === "data-thinking-steps" &&
			areThinkingStepsEqual(existing.data.steps, stepsArray)
		) {
			return false;
		}

		state.contentParts[existingIdx] = {
			type: "data-thinking-steps",
			data: { steps: stepsArray },
		};
		return true;
	} else {
		state.contentParts.unshift({
			type: "data-thinking-steps",
			data: { steps: stepsArray },
		});
		if (state.currentTextPartIndex >= 0) {
			state.currentTextPartIndex += 1;
		}
		if (state.currentReasoningPartIndex >= 0) {
			state.currentReasoningPartIndex += 1;
		}
		for (const [id, idx] of state.toolCallIndices) {
			state.toolCallIndices.set(id, idx + 1);
		}
		return true;
	}
}

/**
 * Coalesces rapid setMessages calls into at most one React state update per
 * throttle interval. During streaming, SSE text-delta events arrive much
 * faster than the user can perceive; throttling to ~50 ms lets React +
 * ReactMarkdown do far fewer reconciliation passes, eliminating flicker.
 */
export class FrameBatchedUpdater {
	private timerId: ReturnType<typeof setTimeout> | null = null;
	private flusher: (() => void) | null = null;
	private dirty = false;
	private static readonly INTERVAL_MS = 50;

	/** Mark state as dirty — will flush after the throttle interval. */
	schedule(flush: () => void): void {
		this.flusher = flush;
		this.dirty = true;
		if (this.timerId === null) {
			this.timerId = setTimeout(() => {
				this.timerId = null;
				if (this.dirty) {
					this.dirty = false;
					this.flusher?.();
				}
			}, FrameBatchedUpdater.INTERVAL_MS);
		}
	}

	/** Immediately flush any pending update (call on tool events or stream end). */
	flush(): void {
		if (this.timerId !== null) {
			clearTimeout(this.timerId);
			this.timerId = null;
		}
		if (this.dirty) {
			this.dirty = false;
			this.flusher?.();
		}
	}

	dispose(): void {
		if (this.timerId !== null) {
			clearTimeout(this.timerId);
			this.timerId = null;
		}
		this.dirty = false;
		this.flusher = null;
	}
}

export function appendText(state: ContentPartsState, delta: string): void {
	// First text delta after a reasoning block: close the reasoning so
	// the assistant-ui renderer treats them as separate parts (the
	// reasoning block collapses; the answer streams below).
	if (state.currentReasoningPartIndex >= 0) {
		state.currentReasoningPartIndex = -1;
	}
	if (
		state.currentTextPartIndex >= 0 &&
		state.contentParts[state.currentTextPartIndex]?.type === "text"
	) {
		(state.contentParts[state.currentTextPartIndex] as { type: "text"; text: string }).text +=
			delta;
	} else {
		state.contentParts.push({ type: "text", text: delta });
		state.currentTextPartIndex = state.contentParts.length - 1;
	}
}

export function appendReasoning(state: ContentPartsState, delta: string): void {
	// Symmetric to appendText: open a fresh reasoning block on first
	// delta, then accumulate into it. ``endReasoning`` simply closes
	// the active block; subsequent reasoning deltas would open a new
	// one (matching ``text-start/end`` semantics on the wire).
	if (state.currentTextPartIndex >= 0) {
		state.currentTextPartIndex = -1;
	}
	if (
		state.currentReasoningPartIndex >= 0 &&
		state.contentParts[state.currentReasoningPartIndex]?.type === "reasoning"
	) {
		(
			state.contentParts[state.currentReasoningPartIndex] as {
				type: "reasoning";
				text: string;
			}
		).text += delta;
	} else {
		state.contentParts.push({ type: "reasoning", text: delta });
		state.currentReasoningPartIndex = state.contentParts.length - 1;
	}
}

export function endReasoning(state: ContentPartsState): void {
	state.currentReasoningPartIndex = -1;
}

export function addStepSeparator(state: ContentPartsState): void {
	// Push a divider between consecutive model steps within a single
	// assistant turn. We only emit it when the message already has
	// non-step content (so the FIRST step of a turn doesn't
	// generate a leading separator) and when the previous part isn't
	// itself a separator (defensive against duplicate `start-step`
	// events).
	const hasContent = state.contentParts.some(
		(p) => p.type === "text" || p.type === "reasoning" || p.type === "tool-call"
	);
	if (!hasContent) return;
	const last = state.contentParts[state.contentParts.length - 1];
	if (last && last.type === "data-step-separator") return;

	const stepIndex = state.contentParts.filter((p) => p.type === "data-step-separator").length;
	state.contentParts.push({ type: "data-step-separator", data: { stepIndex } });
	state.currentTextPartIndex = -1;
	state.currentReasoningPartIndex = -1;
}

/**
 * Allowlist of tool names that should produce a UI tool card. The
 * sentinel ``"all"`` matches every tool — we dropped the legacy
 * ``BASE_TOOLS_WITH_UI`` gate so that ALL tool calls render via the
 * generic ``ToolFallback``. The backend's ``format_thinking_step``
 * summarisation and the defensive ``result_length``-only default for
 * unknown tools keep persisted message JSON from ballooning.
 */
export type ToolUIGate = Set<string> | "all";

function _toolPasses(gate: ToolUIGate, toolName: string): boolean {
	return gate === "all" || gate.has(toolName);
}

export function addToolCall(
	state: ContentPartsState,
	toolsWithUI: ToolUIGate,
	toolCallId: string,
	toolName: string,
	args: Record<string, unknown>,
	force = false,
	langchainToolCallId?: string
): void {
	if (force || _toolPasses(toolsWithUI, toolName)) {
		state.contentParts.push({
			type: "tool-call",
			toolCallId,
			toolName,
			args,
			...(langchainToolCallId ? { langchainToolCallId } : {}),
		});
		state.toolCallIndices.set(toolCallId, state.contentParts.length - 1);
		state.currentTextPartIndex = -1;
		state.currentReasoningPartIndex = -1;
	}
}

/**
 * Reverse-lookup helper used by the SSE ``data-action-log`` handler:
 * given the LangChain ``tool_call.id`` (set on the content part as
 * ``langchainToolCallId``), return the synthetic ``toolCallId`` that
 * the chat tool card uses (``call_<run-id>``). Returns ``null`` when no
 * matching tool card has been seen yet — the action is still recorded
 * in the LC-id-keyed atom so the card can pick it up when it eventually
 * arrives.
 */
export function findToolCallIdByLcId(
	state: ContentPartsState,
	lcToolCallId: string
): string | null {
	for (const part of state.contentParts) {
		if (part.type === "tool-call" && part.langchainToolCallId === lcToolCallId) {
			return part.toolCallId;
		}
	}
	return null;
}

export function updateToolCall(
	state: ContentPartsState,
	toolCallId: string,
	update: {
		args?: Record<string, unknown>;
		argsText?: string;
		result?: unknown;
		langchainToolCallId?: string;
	}
): void {
	const index = state.toolCallIndices.get(toolCallId);
	if (index !== undefined && state.contentParts[index]?.type === "tool-call") {
		const tc = state.contentParts[index] as ContentPart & { type: "tool-call" };
		if (update.args) tc.args = update.args;
		// ``!== undefined`` (NOT a truthy check): an explicit empty
		// string CAN clear, and a finalization with
		// ``JSON.stringify({}, null, 2) === "{}"`` (truthy but
		// represents an empty-input call) still applies.
		if (update.argsText !== undefined) tc.argsText = update.argsText;
		if (update.result !== undefined) tc.result = update.result;
		// Only backfill langchainToolCallId if not already set — the
		// authoritative ``on_tool_end`` value should override an earlier
		// best-effort match, but a NULL late-arriving value should not
		// blow away a known good early one.
		if (update.langchainToolCallId && !tc.langchainToolCallId) {
			tc.langchainToolCallId = update.langchainToolCallId;
		}
	}
}

/**
 * Append a streamed args-delta chunk to the active tool call's
 * ``argsText``. No-ops when no card has been registered yet for the
 * given ``toolCallId`` (the matching ``tool-input-start`` either lost
 * the wire race or this id never had a card — either way the deltas
 * have nowhere safe to land).
 */
export function appendToolInputDelta(
	state: ContentPartsState,
	toolCallId: string,
	delta: string
): void {
	const idx = state.toolCallIndices.get(toolCallId);
	if (idx === undefined) return;
	const tc = state.contentParts[idx];
	if (tc?.type !== "tool-call") return;
	tc.argsText = (tc.argsText ?? "") + delta;
}

function _hasInterruptResult(part: ContentPart): boolean {
	if (part.type !== "tool-call") return false;
	const r = (part as { result?: unknown }).result;
	return typeof r === "object" && r !== null && "__interrupt__" in r;
}

export function buildContentForUI(
	state: ContentPartsState,
	toolsWithUI: ToolUIGate
): ThreadMessageLike["content"] {
	const filtered = state.contentParts.filter((part) => {
		if (part.type === "text") return part.text.length > 0;
		if (part.type === "reasoning") return part.text.length > 0;
		if (part.type === "tool-call")
			return _toolPasses(toolsWithUI, part.toolName) || _hasInterruptResult(part);
		if (part.type === "data-thinking-steps") return true;
		if (part.type === "data-step-separator") return true;
		return false;
	});
	return filtered.length > 0
		? (filtered as ThreadMessageLike["content"])
		: [{ type: "text", text: "" }];
}

export function buildContentForPersistence(
	state: ContentPartsState,
	toolsWithUI: ToolUIGate
): unknown[] {
	const parts: unknown[] = [];

	for (const part of state.contentParts) {
		if (part.type === "text" && part.text.length > 0) {
			parts.push(part);
		} else if (part.type === "reasoning" && part.text.length > 0) {
			// Persist reasoning blocks so a chat reload re-renders the
			// collapsed thinking section instead of
			// silently dropping it (mirrors the data-thinking-steps
			// branch above).
			parts.push(part);
		} else if (
			part.type === "tool-call" &&
			(_toolPasses(toolsWithUI, part.toolName) || _hasInterruptResult(part))
		) {
			parts.push(part);
		} else if (part.type === "data-thinking-steps") {
			parts.push(part);
		} else if (part.type === "data-step-separator") {
			parts.push(part);
		}
	}

	return parts.length > 0 ? parts : [{ type: "text", text: "" }];
}

export type SSEEvent =
	| { type: "start"; messageId?: string }
	| { type: "finish" }
	| { type: "start-step" }
	| { type: "finish-step" }
	| { type: "text-start"; id: string }
	| { type: "text-delta"; id?: string; delta: string }
	| { type: "text-end"; id: string }
	| { type: "reasoning-start"; id: string }
	| { type: "reasoning-delta"; id?: string; delta: string }
	| { type: "reasoning-end"; id: string }
	| {
			type: "tool-input-start";
			toolCallId: string;
			toolName: string;
			/** Authoritative LangChain ``tool_call.id``. Optional. */
			langchainToolCallId?: string;
	  }
	| {
			/**
			 * Live tool-call argument delta. Concatenated into
			 * ``argsText`` on the matching ``tool-call`` content part
			 * by ``appendToolInputDelta``. parity_v2 only — the legacy
			 * code path emits ``tool-input-available`` without prior
			 * deltas.
			 */
			type: "tool-input-delta";
			toolCallId: string;
			inputTextDelta: string;
	  }
	| {
			type: "tool-input-available";
			toolCallId: string;
			toolName: string;
			input: Record<string, unknown>;
			langchainToolCallId?: string;
	  }
	| {
			type: "tool-output-available";
			toolCallId: string;
			output: Record<string, unknown>;
			/** Authoritative LangChain ``tool_call.id`` extracted from
			 * ``ToolMessage.tool_call_id`` at on_tool_end. Backfills cards
			 * that didn't get the id at tool-input-start time. */
			langchainToolCallId?: string;
	  }
	| { type: "data-thinking-step"; data: ThinkingStepData }
	| { type: "data-thread-title-update"; data: { threadId: number; title: string } }
	| { type: "data-interrupt-request"; data: Record<string, unknown> }
	| { type: "data-documents-updated"; data: Record<string, unknown> }
	| {
			/**
			 * A freshly committed AgentActionLog row. Frontend stores
			 * this in a Map keyed off ``lc_tool_call_id`` so the chat
			 * tool card can light up its Revert button.
			 */
			type: "data-action-log";
			data: {
				id: number;
				lc_tool_call_id: string | null;
				chat_turn_id: string | null;
				tool_name: string;
				reversible: boolean;
				reverse_descriptor_present: boolean;
				created_at: string | null;
				error: boolean;
			};
	  }
	| {
			/**
			 * Reversibility flipped (filesystem op SAVEPOINT committed;
			 * cf. ``kb_persistence._dispatch_reversibility_update``).
			 */
			type: "data-action-log-updated";
			data: { id: number; reversible: boolean };
	  }
	| {
			/**
			 * Emitted at the start of every stream so the frontend can
			 * stamp the per-turn correlation id onto the in-flight
			 * assistant message and replay it via
			 * ``appendMessage``. Pure-text turns never produce
			 * action-log events; this event guarantees the frontend
			 * always learns the turn id.
			 */
			type: "data-turn-info";
			data: { chat_turn_id: string };
	  }
	| {
			/**
			 * Best-effort revert pass that ran BEFORE this regeneration.
			 * Per-action results are forwarded to the UI so the user
			 * can see which downstream actions were rolled
			 * back vs which couldn't be undone.
			 */
			type: "data-revert-results";
			data: {
				status: "ok" | "partial";
				chat_turn_ids: string[];
				total: number;
				reverted: number;
				already_reverted: number;
				not_reversible: number;
				/**
				 * ``permission_denied`` and ``skipped`` are first-class
				 * counters so the response invariant
				 * ``total === sum(counters)`` always holds. Optional
				 * for forward compatibility with older backends; the
				 * frontend treats missing values as ``0``.
				 */
				permission_denied?: number;
				failed: number;
				skipped?: number;
				results: Array<{
					action_id: number;
					tool_name: string;
					status:
						| "reverted"
						| "already_reverted"
						| "not_reversible"
						| "permission_denied"
						| "failed"
						| "skipped";
					message?: string | null;
					new_action_id?: number | null;
					error?: string | null;
				}>;
			};
	  }
	| {
			type: "data-token-usage";
			data: {
				usage: Record<
					string,
					{ prompt_tokens: number; completion_tokens: number; total_tokens: number }
				>;
				prompt_tokens: number;
				completion_tokens: number;
				total_tokens: number;
				call_details: Array<{
					model: string;
					prompt_tokens: number;
					completion_tokens: number;
					total_tokens: number;
				}>;
			};
	  }
	| { type: "error"; errorText: string; errorCode?: string };

/**
 * Async generator that reads an SSE stream and yields parsed JSON objects.
 * Handles buffering, event splitting, and skips malformed JSON / [DONE] lines.
 */
export async function* readSSEStream(response: Response): AsyncGenerator<SSEEvent> {
	if (!response.body) {
		throw new Error("No response body");
	}

	const reader = response.body.getReader();
	const decoder = new TextDecoder();
	let buffer = "";

	try {
		while (true) {
			const { done, value } = await reader.read();
			if (done) break;

			buffer += decoder.decode(value, { stream: true });
			const events = buffer.split(/\r?\n\r?\n/);
			buffer = events.pop() || "";

			for (const event of events) {
				const lines = event.split(/\r?\n/);
				for (const line of lines) {
					if (!line.startsWith("data: ")) continue;
					const data = line.slice(6).trim();
					if (!data || data === "[DONE]") continue;

					try {
						yield JSON.parse(data);
					} catch (e) {
						if (e instanceof SyntaxError) continue;
						throw e;
					}
				}
			}
		}
	} finally {
		reader.releaseLock();
	}
}
