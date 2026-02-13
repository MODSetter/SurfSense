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
	  };

export interface ContentPartsState {
	contentParts: ContentPart[];
	currentTextPartIndex: number;
	toolCallIndices: Map<string, number>;
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
		return false;
	});
	return filtered.length > 0
		? (filtered as ThreadMessageLike["content"])
		: [{ type: "text", text: "" }];
}

export function buildContentForPersistence(
	state: ContentPartsState,
	toolsWithUI: Set<string>,
	currentThinkingSteps: Map<string, ThinkingStepData>
): unknown[] {
	const parts: unknown[] = [];

	if (currentThinkingSteps.size > 0) {
		parts.push({
			type: "thinking-steps",
			steps: Array.from(currentThinkingSteps.values()),
		});
	}

	for (const part of state.contentParts) {
		if (part.type === "text" && part.text.length > 0) {
			parts.push(part);
		} else if (part.type === "tool-call" && toolsWithUI.has(part.toolName)) {
			parts.push(part);
		}
	}

	return parts.length > 0 ? parts : [{ type: "text", text: "" }];
}

/**
 * Async generator that reads an SSE stream and yields parsed JSON objects.
 * Handles buffering, event splitting, and skips malformed JSON / [DONE] lines.
 */
export async function* readSSEStream(response: Response): AsyncGenerator<any> {
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
