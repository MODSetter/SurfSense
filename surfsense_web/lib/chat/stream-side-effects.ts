import type { ThreadMessageLike } from "@assistant-ui/react";
import {
	addToolCall,
	type ContentPartsState,
	type ToolUIGate,
	updateToolCall,
} from "@/lib/chat/streaming-state";

type InterruptActionRequest = {
	name: string;
	args: Record<string, unknown>;
};

export type EditedInterruptAction = {
	name: string;
	args: Record<string, unknown>;
};

function readInterruptActions(interruptData: Record<string, unknown>): InterruptActionRequest[] {
	return (interruptData.action_requests ?? []) as InterruptActionRequest[];
}

/**
 * Applies an interrupt request payload to tool-call parts. Existing tool cards
 * are updated in-place; missing ones are upserted so approval UI always shows.
 */
export function applyInterruptRequestToContentParts(
	contentPartsState: ContentPartsState,
	toolsWithUI: ToolUIGate,
	interruptData: Record<string, unknown>
): void {
	const { contentParts, toolCallIndices } = contentPartsState;
	const actionRequests = readInterruptActions(interruptData);
	for (const action of actionRequests) {
		const existingEntry = Array.from(toolCallIndices.entries()).find(([, idx]) => {
			const part = contentParts[idx];
			return part?.type === "tool-call" && part.toolName === action.name;
		});

		if (existingEntry) {
			updateToolCall(contentPartsState, existingEntry[0], {
				result: { __interrupt__: true, ...interruptData },
			});
		} else {
			const toolCallId = `interrupt-${action.name}`;
			addToolCall(contentPartsState, toolsWithUI, toolCallId, action.name, action.args, true);
			updateToolCall(contentPartsState, toolCallId, {
				result: { __interrupt__: true, ...interruptData },
			});
		}
	}
}

export function mergeEditedInterruptAction(
	contentParts: ContentPartsState["contentParts"],
	editedAction: EditedInterruptAction | undefined
): void {
	if (!editedAction) return;
	for (const part of contentParts) {
		if (part.type === "tool-call" && part.toolName === editedAction.name) {
			const mergedArgs = { ...part.args, ...editedAction.args };
			part.args = mergedArgs;
			// assistant-ui prefers argsText over JSON.stringify(args)
			part.argsText = JSON.stringify(mergedArgs, null, 2);
			break;
		}
	}
}

export function markInterruptDecisionOnContentParts(
	contentParts: ContentPartsState["contentParts"],
	decisionType: "approve" | "reject" | undefined
): void {
	if (!decisionType) return;
	for (const part of contentParts) {
		if (
			part.type === "tool-call" &&
			typeof part.result === "object" &&
			part.result !== null &&
			"__interrupt__" in (part.result as Record<string, unknown>)
		) {
			part.result = {
				...(part.result as Record<string, unknown>),
				__decided__: decisionType,
			};
		}
	}
}

/**
 * When a streamed message is persisted, the backend returns the durable
 * turn_id; merge it into assistant-ui metadata for turn-scoped actions.
 */
export function mergeChatTurnIdIntoMessage(
	msg: ThreadMessageLike,
	turnId: string | null | undefined
): ThreadMessageLike {
	if (!turnId) return msg;
	const existingMeta = (msg.metadata ?? {}) as { custom?: Record<string, unknown> };
	const existingCustom = existingMeta.custom ?? {};
	if ((existingCustom as { chatTurnId?: string }).chatTurnId === turnId) return msg;
	return {
		...msg,
		metadata: {
			...existingMeta,
			custom: { ...existingCustom, chatTurnId: turnId },
		},
	};
}

export function readStreamedChatTurnId(data: unknown): string | null {
	if (typeof data !== "object" || data === null) return null;
	const value = (data as { chat_turn_id?: unknown }).chat_turn_id;
	return typeof value === "string" && value.length > 0 ? value : null;
}

/**
 * Parse the payload of `data-user-message-id` / `data-assistant-message-id`
 * SSE events emitted by `stream_new_chat` and `stream_resume_chat` after
 * `persist_user_turn` / `persist_assistant_shell` resolve a canonical
 * `new_chat_messages.id`. Mirrors {@link readStreamedChatTurnId}.
 *
 * Returns `null` when the payload is malformed (missing or non-numeric
 * `message_id`); callers should treat this as "ignore the event" so a
 * malformed BE payload never overwrites the optimistic id with a bogus
 * value.
 */
export function readStreamedMessageId(
	data: unknown
): { messageId: number; turnId: string | null } | null {
	if (typeof data !== "object" || data === null) return null;
	const obj = data as { message_id?: unknown; turn_id?: unknown };
	if (typeof obj.message_id !== "number" || !Number.isFinite(obj.message_id)) {
		return null;
	}
	const turnId = typeof obj.turn_id === "string" && obj.turn_id.length > 0 ? obj.turn_id : null;
	return { messageId: obj.message_id, turnId };
}

export function applyTurnIdToAssistantMessageList(
	messages: ThreadMessageLike[],
	assistantMsgId: string,
	turnId: string
): ThreadMessageLike[] {
	return messages.map((m) => (m.id === assistantMsgId ? mergeChatTurnIdIntoMessage(m, turnId) : m));
}
