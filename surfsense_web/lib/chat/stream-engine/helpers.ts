import { z } from "zod";
import type { MentionedDocumentInfo } from "@/atoms/chat/mentioned-documents.atom";
import type { ToolUIGate } from "@/lib/chat/streaming-state";

/**
 * Every tool call renders a card. The sentinel ``"all"`` matches every tool
 * — the legacy ``BASE_TOOLS_WITH_UI`` allowlist was dropped so unknown tool
 * calls route through the generic ``ToolFallback``. Persisted payload size
 * stays bounded because the backend's ``format_thinking_step`` summarisation
 * and the ``result_length``-only default for unknown tools keep the JSON
 * from ballooning.
 */
export const TOOLS_WITH_UI_ALL: ToolUIGate = "all";

export const TURN_CANCELLING_INITIAL_DELAY_MS = 200;
export const TURN_CANCELLING_BACKOFF_FACTOR = 2;
export const TURN_CANCELLING_MAX_DELAY_MS = 1500;
export const RECENT_CANCEL_WINDOW_MS = 5_000;

export function sleep(ms: number): Promise<void> {
	return new Promise((resolve) => setTimeout(resolve, ms));
}

export function computeFallbackTurnCancellingRetryDelay(attempt: number): number {
	const safeAttempt = Math.max(1, attempt);
	const raw =
		TURN_CANCELLING_INITIAL_DELAY_MS * TURN_CANCELLING_BACKOFF_FACTOR ** (safeAttempt - 1);
	return Math.min(raw, TURN_CANCELLING_MAX_DELAY_MS);
}

/**
 * Generate a synthetic ``toolCallId`` for an action_request that has no
 * matching streamed tool-call card (HITL-blocked subagent calls don't surface
 * as tool-call events). Suffixes a counter when the base id is already taken
 * — sequential interrupts for the same tool name otherwise collide on
 * ``interrupt-${name}-${i}`` and crash assistant-ui with a duplicate-key error.
 */
export function freshSynthToolCallId(
	toolCallIndices: Map<string, number>,
	toolName: string,
	index: number
): string {
	const base = `interrupt-${toolName}-${index}`;
	if (!toolCallIndices.has(base)) return base;
	let n = 1;
	while (toolCallIndices.has(`${base}-${n}`)) n++;
	return `${base}-${n}`;
}

/**
 * Pair each ``action_request`` to a unique pending tool-call card, preserving
 * order so ``decisions[i]`` lines up with ``action_requests[i]`` on the wire.
 *
 * Same-name bundles (e.g. three ``create_jira_issue``) used to collapse onto
 * one card because the matcher keyed by name; this consumes each card via the
 * ``claimed`` set and walks forward in DOM order.
 */
export function pairBundleToolCallIds(
	toolCallIndices: Map<string, number>,
	contentParts: Array<{
		type: string;
		toolName?: string;
		result?: unknown;
	}>,
	actionRequests: ReadonlyArray<{ name: string }>
): Array<string | null> {
	const claimed = new Set<string>();
	const paired: Array<string | null> = [];
	for (const action of actionRequests) {
		let matched: string | null = null;
		for (const [tcId, idx] of toolCallIndices) {
			if (claimed.has(tcId)) continue;
			const part = contentParts[idx];
			if (!part || part.type !== "tool-call" || part.toolName !== action.name) continue;
			const result = part.result as Record<string, unknown> | undefined | null;
			if (result == null || (result.__interrupt__ === true && !result.__decided__)) {
				matched = tcId;
				claimed.add(tcId);
				break;
			}
		}
		paired.push(matched);
	}
	return paired;
}

/**
 * Zod schema for mentioned document info (for type-safe parsing).
 *
 * ``kind`` defaults to ``"doc"`` so messages persisted before folder
 * mentions existed deserialise unchanged.
 */
const MentionedDocumentInfoSchema = z.object({
	id: z.number(),
	title: z.string(),
	document_type: z.string().optional(),
	kind: z
		.union([z.literal("doc"), z.literal("folder"), z.literal("connector"), z.literal("thread")])
		.optional()
		.default("doc"),
	connector_type: z.string().optional(),
	account_name: z.string().optional(),
});

const MentionedDocumentsPartSchema = z.object({
	type: z.literal("mentioned-documents"),
	documents: z.array(MentionedDocumentInfoSchema),
});

/**
 * Extract mentioned documents from message content (type-safe with Zod).
 */
export function extractMentionedDocuments(content: unknown): MentionedDocumentInfo[] {
	if (!Array.isArray(content)) return [];

	for (const part of content) {
		const result = MentionedDocumentsPartSchema.safeParse(part);
		if (result.success) {
			return result.data.documents.map<MentionedDocumentInfo>((doc) => {
				if (doc.kind === "connector") {
					return {
						id: doc.id,
						title: doc.title,
						kind: "connector",
						connector_type: doc.connector_type ?? doc.document_type ?? "UNKNOWN",
						account_name: doc.account_name ?? doc.title,
					};
				}
				if (doc.kind === "folder") {
					return {
						id: doc.id,
						title: doc.title,
						kind: "folder",
					};
				}
				if (doc.kind === "thread") {
					return {
						id: doc.id,
						title: doc.title,
						kind: "thread",
					};
				}
				return {
					id: doc.id,
					title: doc.title,
					document_type: doc.document_type ?? "UNKNOWN",
					kind: "doc",
				};
			});
		}
	}

	return [];
}
