import type { ThreadMessageLike } from "@assistant-ui/react";
import type { MessageRecord } from "./thread-persistence";

/** Minimal shape used by ``filterSupersededAbortedMessages``. */
interface AbortableMessage {
	id: number;
	role: string;
	content: unknown;
	turn_id?: string | null;
}

/**
 * True when the row is a frozen interrupt frame: an assistant message
 * whose tool-calls all carry ``state: "aborted"``. A single non-aborted
 * tool-call disqualifies (defensive against future mixed states).
 */
function isAbortedAssistantMessage(msg: AbortableMessage): boolean {
	if (msg.role.toLowerCase() !== "assistant") return false;
	if (!Array.isArray(msg.content)) return false;
	let hasToolCalls = false;
	for (const part of msg.content) {
		if (typeof part !== "object" || part === null) continue;
		if ((part as { type?: string }).type !== "tool-call") continue;
		hasToolCalls = true;
		if ((part as { state?: unknown }).state !== "aborted") return false;
	}
	return hasToolCalls;
}

/**
 * Positional supersede check: an aborted assistant row is superseded
 * iff another assistant row appears later before any user row.
 *
 * NOT turn-id-based: ``stream_resume_chat`` allocates a fresh
 * ``turn_id`` for the resumed row, so interrupt+resume rows never
 * share a turn_id. Conversational adjacency is the reliable signal —
 * an assistant→assistant pair without a user row between them is the
 * unique signature of an interrupt+resume cycle.
 */
function isSupersededByLaterAssistant<T extends AbortableMessage>(
	messages: readonly T[],
	idx: number
): boolean {
	for (let i = idx + 1; i < messages.length; i++) {
		const role = messages[i].role.toLowerCase();
		if (role === "user") return false;
		if (role === "assistant") return true;
	}
	return false;
}

/**
 * Drop frozen interrupt-frame rows once they have a resumed
 * continuation. Pure (returns a new array). Caller passes messages in
 * chronological order.
 *
 * Never-resumed aborts are preserved (user navigated away mid-decision)
 * so the user still sees what happened.
 */
export function filterSupersededAbortedMessages<T extends AbortableMessage>(
	messages: readonly T[]
): T[] {
	return messages.filter((msg, idx) => {
		if (!isAbortedAssistantMessage(msg)) return true;
		return !isSupersededByLaterAssistant(messages, idx);
	});
}

/**
 * Convert a backend ``MessageRecord`` to assistant-ui's
 * ``ThreadMessageLike``. Also migrates legacy ``thinking-steps`` parts
 * to ``data-thinking-steps``.
 */
export function convertToThreadMessage(msg: MessageRecord): ThreadMessageLike {
	let content: ThreadMessageLike["content"];

	if (typeof msg.content === "string") {
		content = [{ type: "text", text: msg.content }];
	} else if (Array.isArray(msg.content)) {
		const convertedContent = msg.content
			.filter((part: unknown) => {
				if (typeof part !== "object" || part === null || !("type" in part)) return true;
				const partType = (part as { type: string }).type;
				return partType !== "mentioned-documents" && partType !== "attachments";
			})
			.map((part: unknown) => {
				if (
					typeof part === "object" &&
					part !== null &&
					"type" in part &&
					(part as { type: string }).type === "thinking-steps"
				) {
					const steps = (part as unknown as { steps?: unknown[] }).steps;
					return {
						type: "data-thinking-steps",
						data: { steps: Array.isArray(steps) ? steps : [] },
					};
				}
				return part;
			});
		content =
			convertedContent.length > 0
				? (convertedContent as ThreadMessageLike["content"])
				: [{ type: "text", text: "" }];
	} else {
		content = [{ type: "text", text: String(msg.content) }];
	}

	const metadata =
		msg.author_id || msg.token_usage || msg.turn_id
			? {
					custom: {
						...(msg.author_id && {
							author: {
								displayName: msg.author_display_name ?? null,
								avatarUrl: msg.author_avatar_url ?? null,
							},
						}),
						...(msg.token_usage && { usage: msg.token_usage }),
						// Surfaced for the assistant footer's per-turn
						// "Revert turn" button. Null on legacy rows.
						...(msg.turn_id && { chatTurnId: msg.turn_id }),
					},
				}
			: undefined;

	return {
		id: `msg-${msg.id}`,
		role: msg.role,
		content,
		createdAt: new Date(msg.created_at),
		metadata,
	};
}
