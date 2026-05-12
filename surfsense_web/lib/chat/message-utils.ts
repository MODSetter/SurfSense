import type { ThreadMessageLike } from "@assistant-ui/react";
import type { MessageRecord } from "./thread-persistence";

/** Minimal shape used by the interrupt/resume reconciler. */
interface AbortableMessage {
	id: number;
	role: string;
	content: unknown;
	turn_id?: string | null;
}

function isAssistant(msg: AbortableMessage): boolean {
	return msg.role.toLowerCase() === "assistant";
}

/** True when the row carries at least one tool-call with ``state: "aborted"``. */
function hasAbortedToolCall(msg: AbortableMessage): boolean {
	if (!isAssistant(msg) || !Array.isArray(msg.content)) return false;
	for (const part of msg.content) {
		if (typeof part !== "object" || part === null) continue;
		if ((part as { type?: string }).type !== "tool-call") continue;
		if ((part as { state?: unknown }).state === "aborted") return true;
	}
	return false;
}

/**
 * True when EVERY tool-call on the row is aborted. The row is then a
 * frozen interrupt frame with no salvageable activity — safe to drop
 * outright.
 */
function isFullyAbortedAssistantMessage(msg: AbortableMessage): boolean {
	if (!isAssistant(msg) || !Array.isArray(msg.content)) return false;
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
 * Locate the resume row that supersedes ``messages[idx]``. The
 * ``stream_resume_chat`` flow allocates a fresh ``turn_id`` so we
 * can't pair on it; conversational adjacency (assistant → assistant
 * with no user row between) is the unique signature. Skips already-
 * dropped indices so chained interrupt-resumes still pair cleanly.
 */
function findResumeSuccessorIdx<T extends AbortableMessage>(
	messages: readonly T[],
	idx: number,
	dropped: ReadonlySet<number>
): number | null {
	for (let i = idx + 1; i < messages.length; i++) {
		if (dropped.has(i)) continue;
		const role = messages[i].role.toLowerCase();
		if (role === "user") return null;
		if (role === "assistant") return i;
	}
	return null;
}

/** Read ``data.steps`` from either ``data-thinking-steps`` (modern) or ``thinking-steps`` (legacy). */
function extractStepsFromPart(part: unknown): unknown[] | null {
	if (typeof part !== "object" || part === null) return null;
	const p = part as { type?: unknown; data?: unknown; steps?: unknown };
	if (p.type === "data-thinking-steps") {
		const data = p.data as { steps?: unknown } | undefined;
		return Array.isArray(data?.steps) ? data.steps : [];
	}
	if (p.type === "thinking-steps") {
		return Array.isArray(p.steps) ? (p.steps as unknown[]) : [];
	}
	return null;
}

/** Split a content array into (combined steps, all other parts in order). */
function partitionContent(content: unknown): { steps: unknown[]; others: unknown[] } {
	if (!Array.isArray(content)) return { steps: [], others: [] };
	const steps: unknown[] = [];
	const others: unknown[] = [];
	for (const part of content) {
		const partSteps = extractStepsFromPart(part);
		if (partSteps !== null) {
			steps.push(...partSteps);
			continue;
		}
		others.push(part);
	}
	return { steps, others };
}

/**
 * Fold an interrupt-frame row's content into its resume successor so
 * the user sees one assistant turn instead of two stacked bubbles.
 * Successor's metadata wins (id, created_at, turn_id, token_usage,
 * author) — that's the row the per-turn revert button keys to.
 *
 * Order: combined ``data-thinking-steps`` (older steps then newer) at
 * index 0, followed by older's other parts in order, then newer's. The
 * older row's aborted ``task`` wrapper is preserved so the rejected
 * attempt remains visible alongside the successful retry; both spans
 * survive and ``groupItems`` renders them as sibling task branches in
 * one timeline.
 */
function mergeInterruptedIntoResume<T extends AbortableMessage>(older: T, newer: T): T {
	const olderParts = partitionContent(older.content);
	const newerParts = partitionContent(newer.content);

	const mergedSteps = [...olderParts.steps, ...newerParts.steps];
	const mergedContent: unknown[] = [];
	if (mergedSteps.length > 0) {
		mergedContent.push({ type: "data-thinking-steps", data: { steps: mergedSteps } });
	}
	mergedContent.push(...olderParts.others, ...newerParts.others);

	return { ...newer, content: mergedContent };
}

/**
 * Reconcile interrupt-frame and resume rows so the UI shows one
 * assistant turn per user turn even when the backend persists them as
 * separate ``new_chat_messages`` rows.
 *
 * Two cases, both keyed on conversational adjacency (assistant →
 * assistant with no user row between):
 *
 *  - **Fully aborted older row** (every tool-call ``state: "aborted"``,
 *    no salvageable activity) → drop the older row.
 *  - **Partially aborted older row** (mixed completed + aborted, e.g.
 *    inner subagent tools ran before the interrupt) → fold its content
 *    into the successor. Successor metadata wins.
 *
 * Never-resumed aborts (user navigated away mid-decision) survive so
 * the user still sees what happened.
 *
 * Pure: returns a new array with new merged objects when needed.
 * Caller passes messages in chronological order.
 */
export function reconcileInterruptedAssistantMessages<T extends AbortableMessage>(
	messages: readonly T[]
): T[] {
	const dropped = new Set<number>();
	const mergeInto = new Map<number, number[]>();

	for (let i = 0; i < messages.length; i++) {
		if (dropped.has(i)) continue;
		const msg = messages[i];
		if (!hasAbortedToolCall(msg)) continue;

		const successorIdx = findResumeSuccessorIdx(messages, i, dropped);
		if (successorIdx === null) continue;

		dropped.add(i);
		if (!isFullyAbortedAssistantMessage(msg)) {
			const list = mergeInto.get(successorIdx) ?? [];
			list.push(i);
			mergeInto.set(successorIdx, list);
		}
	}

	const result: T[] = [];
	for (let i = 0; i < messages.length; i++) {
		if (dropped.has(i)) continue;
		const olderIdxs = mergeInto.get(i);
		if (olderIdxs && olderIdxs.length > 0) {
			let merged = messages[i];
			for (const olderIdx of olderIdxs) {
				merged = mergeInterruptedIntoResume(messages[olderIdx], merged);
			}
			result.push(merged);
			continue;
		}
		result.push(messages[i]);
	}
	return result;
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
