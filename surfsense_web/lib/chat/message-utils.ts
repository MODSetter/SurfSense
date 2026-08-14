import type { ThreadMessageLike } from "@assistant-ui/react";
import {
	type ActivityData,
	type ActivityStatus,
	type ActivityTimingData,
	parseActivityData,
	parseActivityTimingData,
} from "./streaming-state";
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

const TERMINAL_ACTIVITY_STATUSES = new Set<ActivityStatus>([
	"completed",
	"error",
	"cancelled",
	"interrupted",
]);

/** Split canonical activities from all independently-rendered message parts. */
function partitionContent(content: unknown): {
	activities: ActivityData[];
	timing: ActivityTimingData | null;
	others: unknown[];
} {
	if (!Array.isArray(content)) return { activities: [], timing: null, others: [] };
	const activities: ActivityData[] = [];
	let timing: ActivityTimingData | null = null;
	const others: unknown[] = [];
	for (const part of content) {
		if (typeof part !== "object" || part === null) {
			others.push(part);
			continue;
		}
		const candidate = part as {
			type?: unknown;
			data?: { activities?: unknown; timing?: unknown };
		};
		if (candidate.type === "data-activities") {
			const snapshots = Array.isArray(candidate.data?.activities) ? candidate.data.activities : [];
			for (const snapshot of snapshots) {
				const activity = parseActivityData(snapshot);
				if (activity) activities.push(activity);
			}
			timing = parseActivityTimingData(candidate.data?.timing);
			continue;
		}
		if (candidate.type === "data-thinking-steps" || candidate.type === "thinking-steps") continue;
		others.push(part);
	}
	return { activities, timing, others };
}

/**
 * Fold an interrupt-frame row's content into its resume successor so
 * the user sees one assistant turn instead of two stacked bubbles.
 * Successor's metadata wins (id, created_at, turn_id, token_usage,
 * author) — that's the row the per-turn revert button keys to.
 *
 * Canonical activities merge by ID. A terminal snapshot wins over a
 * nonterminal one across interruption/resume rows; the successor wins
 * ties. Tool-call parts remain independent for HITL and result cards.
 */
function mergeInterruptedIntoResume<T extends AbortableMessage>(older: T, newer: T): T {
	const olderParts = partitionContent(older.content);
	const newerParts = partitionContent(newer.content);

	const mergedActivities = new Map<string, ActivityData>();
	for (const activity of [...olderParts.activities, ...newerParts.activities]) {
		const current = mergedActivities.get(activity.id);
		if (
			current &&
			TERMINAL_ACTIVITY_STATUSES.has(current.status) &&
			!TERMINAL_ACTIVITY_STATUSES.has(activity.status)
		) {
			continue;
		}
		mergedActivities.set(activity.id, activity);
	}
	const mergedContent: unknown[] = [];
	if (mergedActivities.size > 0 || newerParts.timing || olderParts.timing) {
		mergedContent.push({
			type: "data-activities",
			data: {
				activities: [...mergedActivities.values()].toSorted(
					(a, b) => a.sequence - b.sequence || a.id.localeCompare(b.id)
				),
				...(newerParts.timing || olderParts.timing
					? { timing: newerParts.timing ?? olderParts.timing }
					: {}),
			},
		});
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
 * ``ThreadMessageLike``. Historical thinking-step parts are deliberately hidden.
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
				return (
					partType !== "mentioned-documents" &&
					partType !== "attachments" &&
					partType !== "data-thinking-steps" &&
					partType !== "thinking-steps"
				);
			})
			.map((part: unknown) => {
				if (
					typeof part === "object" &&
					part !== null &&
					"type" in part &&
					(part as { type: string }).type === "status"
				) {
					const text = (part as { text?: unknown }).text;
					return {
						type: "text",
						text: typeof text === "string" ? text : "No response was produced.",
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
						...(msg.turn_id && {
							chatTurnId: msg.turn_id,
						}),
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
