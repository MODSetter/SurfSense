import {
	addStepSeparator,
	addToolCall,
	appendReasoning,
	appendText,
	appendToolInputDelta,
	type ContentPartsState,
	endReasoning,
	readSSEStream,
	type SSEEvent,
	type ThinkingStepData,
	type ToolUIGate,
	updateThinkingSteps,
	updateToolCall,
} from "@/lib/chat/streaming-state";

export type SharedStreamEventContext = {
	contentPartsState: ContentPartsState;
	toolsWithUI: ToolUIGate;
	currentThinkingSteps: Map<string, ThinkingStepData>;
	scheduleFlush: () => void;
	forceFlush: () => void;
	onTokenUsage?: (data: Extract<SSEEvent, { type: "data-token-usage" }>["data"]) => void;
	onToolOutputAvailable?: (
		event: Extract<SSEEvent, { type: "tool-output-available" }>,
		context: {
			contentPartsState: ContentPartsState;
			toolCallIndices: Map<string, number>;
		}
	) => void;
};

/**
 * After a tool produces output, mark any previously-decided interrupt tool
 * calls as completed so the ApprovalCard can transition from shimmer to done.
 */
export function markInterruptsCompleted(
	contentParts: Array<{ type: string; result?: unknown }>
): void {
	for (const part of contentParts) {
		if (
			part.type === "tool-call" &&
			typeof part.result === "object" &&
			part.result !== null &&
			(part.result as Record<string, unknown>).__interrupt__ === true &&
			(part.result as Record<string, unknown>).__decided__ &&
			!(part.result as Record<string, unknown>).__completed__
		) {
			part.result = { ...(part.result as Record<string, unknown>), __completed__: true };
		}
	}
}

export function hasPersistableContent(
	contentParts: ContentPartsState["contentParts"],
	toolsWithUI: ToolUIGate
) {
	return contentParts.some(
		(part) =>
			(part.type === "text" && part.text.length > 0) ||
			(part.type === "reasoning" && part.text.length > 0) ||
			(part.type === "tool-call" && (toolsWithUI === "all" || toolsWithUI.has(part.toolName)))
	);
}

function toStreamTerminalError(
	event: Extract<SSEEvent, { type: "error" }>
): Error & { errorCode?: string } {
	return Object.assign(new Error(event.errorText || "Server error"), {
		errorCode: event.errorCode,
	});
}

export function processSharedStreamEvent(parsed: SSEEvent, context: SharedStreamEventContext): boolean {
	const { contentPartsState, toolsWithUI, currentThinkingSteps, scheduleFlush, forceFlush } = context;
	const { contentParts, toolCallIndices } = contentPartsState;

	switch (parsed.type) {
		case "text-delta":
			appendText(contentPartsState, parsed.delta);
			scheduleFlush();
			return true;

		case "reasoning-delta":
			appendReasoning(contentPartsState, parsed.delta);
			scheduleFlush();
			return true;

		case "reasoning-end":
			endReasoning(contentPartsState);
			scheduleFlush();
			return true;

		case "start-step":
			addStepSeparator(contentPartsState);
			scheduleFlush();
			return true;

		case "finish-step":
			return true;

		case "tool-input-start":
			addToolCall(
				contentPartsState,
				toolsWithUI,
				parsed.toolCallId,
				parsed.toolName,
				{},
				false,
				parsed.langchainToolCallId
			);
			forceFlush();
			return true;

		case "tool-input-delta":
			// High-frequency event: deltas can fire dozens of times per call,
			// so use throttled scheduleFlush (NOT forceFlush) to coalesce.
			appendToolInputDelta(contentPartsState, parsed.toolCallId, parsed.inputTextDelta);
			scheduleFlush();
			return true;

		case "tool-input-available": {
			const finalArgsText = JSON.stringify(parsed.input ?? {}, null, 2);
			if (toolCallIndices.has(parsed.toolCallId)) {
				updateToolCall(contentPartsState, parsed.toolCallId, {
					args: parsed.input || {},
					argsText: finalArgsText,
					langchainToolCallId: parsed.langchainToolCallId,
				});
			} else {
				addToolCall(
					contentPartsState,
					toolsWithUI,
					parsed.toolCallId,
					parsed.toolName,
					parsed.input || {},
					false,
					parsed.langchainToolCallId
				);
				// addToolCall doesn't accept argsText today; backfill via
				// updateToolCall so the new card renders pretty-printed JSON.
				updateToolCall(contentPartsState, parsed.toolCallId, {
					argsText: finalArgsText,
				});
			}
			forceFlush();
			return true;
		}

		case "tool-output-available":
			updateToolCall(contentPartsState, parsed.toolCallId, {
				result: parsed.output,
				langchainToolCallId: parsed.langchainToolCallId,
			});
			markInterruptsCompleted(contentParts);
			context.onToolOutputAvailable?.(parsed, { contentPartsState, toolCallIndices });
			forceFlush();
			return true;

		case "data-thinking-step": {
			const stepData = parsed.data as ThinkingStepData;
			if (stepData?.id) {
				currentThinkingSteps.set(stepData.id, stepData);
				const didUpdate = updateThinkingSteps(contentPartsState, currentThinkingSteps);
				if (didUpdate) {
					scheduleFlush();
				}
			}
			return true;
		}

		case "data-token-usage":
			context.onTokenUsage?.(parsed.data);
			return true;

		case "error":
			throw toStreamTerminalError(parsed);

		default:
			return false;
	}
}

export async function consumeSseEvents(
	response: Response,
	onEvent: (event: SSEEvent) => void | Promise<void>
): Promise<void> {
	for await (const parsed of readSSEStream(response)) {
		await onEvent(parsed);
	}
}
