import type { ThreadMessageLike } from "@assistant-ui/react";

export interface ThinkingStepData {
	id: string;
	title: string;
	status: "pending" | "in_progress" | "completed";
	items: string[];
}

export type ContentPart =
	| { type: "text"; text: string }
	| {
			type: "tool-call";
			toolCallId: string;
			toolName: string;
			args: Record<string, unknown>;
			result?: unknown;
	  }
	| {
			type: "data-thinking-steps";
			data: { steps: ThinkingStepData[] };
	  };

export interface ContentPartsState {
	contentParts: ContentPart[];
	currentTextPartIndex: number;
	toolCallIndices: Map<string, number>;
}

function areThinkingStepsEqual(
	current: ThinkingStepData[],
	next: ThinkingStepData[]
): boolean {
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

export function addToolCall(
	state: ContentPartsState,
	toolsWithUI: Set<string>,
	toolCallId: string,
	toolName: string,
	args: Record<string, unknown>
): void {
	if (toolsWithUI.has(toolName)) {
		state.contentParts.push({
			type: "tool-call",
			toolCallId,
			toolName,
			args,
		});
		state.toolCallIndices.set(toolCallId, state.contentParts.length - 1);
		state.currentTextPartIndex = -1;
	}
}

export function updateToolCall(
	state: ContentPartsState,
	toolCallId: string,
	update: { args?: Record<string, unknown>; result?: unknown }
): void {
	const index = state.toolCallIndices.get(toolCallId);
	if (index !== undefined && state.contentParts[index]?.type === "tool-call") {
		const tc = state.contentParts[index] as ContentPart & { type: "tool-call" };
		if (update.args) tc.args = update.args;
		if (update.result !== undefined) tc.result = update.result;
	}
}

export function buildContentForUI(
	state: ContentPartsState,
	toolsWithUI: Set<string>
): ThreadMessageLike["content"] {
	const filtered = state.contentParts.filter((part) => {
		if (part.type === "text") return part.text.length > 0;
		if (part.type === "tool-call") return toolsWithUI.has(part.toolName);
		if (part.type === "data-thinking-steps") return true;
		return false;
	});
	return filtered.length > 0
		? (filtered as ThreadMessageLike["content"])
		: [{ type: "text", text: "" }];
}

export function buildContentForPersistence(
	state: ContentPartsState,
	toolsWithUI: Set<string>
): unknown[] {
	const parts: unknown[] = [];

	for (const part of state.contentParts) {
		if (part.type === "text" && part.text.length > 0) {
			parts.push(part);
		} else if (part.type === "tool-call" && toolsWithUI.has(part.toolName)) {
			parts.push(part);
		} else if (part.type === "data-thinking-steps") {
			parts.push(part);
		}
	}

	return parts.length > 0 ? parts : [{ type: "text", text: "" }];
}

export type SSEEvent =
	| { type: "text-delta"; delta: string }
	| { type: "tool-input-start"; toolCallId: string; toolName: string }
	| {
			type: "tool-input-available";
			toolCallId: string;
			toolName: string;
			input: Record<string, unknown>;
	  }
	| {
			type: "tool-output-available";
			toolCallId: string;
			output: Record<string, unknown>;
	  }
	| { type: "data-thinking-step"; data: ThinkingStepData }
	| { type: "data-thread-title-update"; data: { threadId: number; title: string } }
	| { type: "data-interrupt-request"; data: Record<string, unknown> }
	| { type: "data-documents-updated"; data: Record<string, unknown> }
	| { type: "error"; errorText: string };

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
