import { toast } from "sonner";
import {
	addToolCall,
	appendReasoning,
	appendText,
	appendToolInputDelta,
	type ContentPartsState,
	endReasoning,
	readSSEStream,
	type SSEEvent,
	startReasoning,
	type ToolUIGate,
	updateToolCall,
	upsertActivity,
	upsertActivityTiming,
} from "@/lib/chat/streaming-state";

export type SharedStreamEventContext = {
	contentPartsState: ContentPartsState;
	toolsWithUI: ToolUIGate;
	scheduleFlush: () => void;
	forceFlush: () => void;
	onTokenUsage?: (data: Extract<SSEEvent, { type: "data-token-usage" }>["data"]) => void;
	onTurnStatus?: (data: Extract<SSEEvent, { type: "data-turn-status" }>["data"]) => void;
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

function toStreamTerminalError(
	event: Extract<SSEEvent, { type: "error" }>
): Error & { errorCode?: string; diagnostic?: string } {
	return Object.assign(new Error(event.message), {
		errorCode: event.errorCode,
		diagnostic: event.diagnostic,
	});
}

export function processSharedStreamEvent(
	parsed: SSEEvent,
	context: SharedStreamEventContext
): boolean {
	const { contentPartsState, toolsWithUI, scheduleFlush, forceFlush } = context;
	const { contentParts, toolCallIndices } = contentPartsState;

	switch (parsed.type) {
		case "reasoning-start":
			startReasoning(contentPartsState, parsed.id, parsed.startedAt);
			scheduleFlush();
			return true;

		case "text-delta":
			appendText(contentPartsState, parsed.delta);
			scheduleFlush();
			return true;

		case "reasoning-delta":
			appendReasoning(contentPartsState, parsed.delta);
			scheduleFlush();
			return true;

		case "reasoning-end":
			endReasoning(contentPartsState, parsed.id, parsed.completedAt);
			scheduleFlush();
			return true;

		case "start-step":
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
				parsed.langchainToolCallId,
				parsed.metadata
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
					metadata: parsed.metadata,
				});
			} else {
				addToolCall(
					contentPartsState,
					toolsWithUI,
					parsed.toolCallId,
					parsed.toolName,
					parsed.input || {},
					false,
					parsed.langchainToolCallId,
					parsed.metadata
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
				metadata: parsed.metadata,
			});
			markInterruptsCompleted(contentParts);
			context.onToolOutputAvailable?.(parsed, { contentPartsState, toolCallIndices });
			forceFlush();
			return true;

		case "data-activity": {
			if (upsertActivity(contentPartsState, parsed.data)) scheduleFlush();
			return true;
		}

		case "data-activity-timing": {
			if (upsertActivityTiming(contentPartsState, parsed.data, performance.now())) scheduleFlush();
			return true;
		}

		case "data-token-usage":
			if (parsed.data.truncated) {
				toast.warning("Response was cut off — the model hit its output-token limit.", {
					duration: Infinity,
					closeButton: true,
				});
			}
			context.onTokenUsage?.(parsed.data);
			return true;

		case "data-turn-status":
			context.onTurnStatus?.(parsed.data);
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
