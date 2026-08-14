import type { ItemStatus, ReasoningItem, TimelineItem, ToolCallItem } from "./types";

/**
 * Structural shape of the relay's ``data-thinking-step`` payload.
 * Declared here (not imported) so the builder stays free of the
 * legacy ``thinking-steps.tsx`` dependency.
 */
export interface ThinkingStepInput {
	id: string;
	title: string;
	items: string[];
	status: "pending" | "in_progress" | "completed" | "error" | "cancelled" | "interrupted";
	metadata?: Record<string, unknown>;
}

/** Narrowed tool-call shape; the assistant-ui content type is wider. */
interface ToolCallPart {
	type: "tool-call";
	toolCallId: string;
	toolName: string;
	args?: Record<string, unknown>;
	argsText?: string;
	result?: unknown;
	langchainToolCallId?: string;
	metadata?: Record<string, unknown>;
}

function isToolCallPart(part: unknown): part is ToolCallPart {
	if (!part || typeof part !== "object") return false;
	const o = part as { type?: unknown; toolCallId?: unknown; toolName?: unknown };
	return (
		o.type === "tool-call" && typeof o.toolCallId === "string" && typeof o.toolName === "string"
	);
}

function asNonEmptyString(v: unknown): string | undefined {
	return typeof v === "string" && v.trim().length > 0 ? v.trim() : undefined;
}

function asFiniteNumber(v: unknown): number | undefined {
	return typeof v === "number" && Number.isFinite(v) ? v : undefined;
}

function extractPresentationMetadata(metadata: Record<string, unknown> | undefined) {
	const integrationValue = metadata?.integration;
	const integration =
		typeof integrationValue === "object" && integrationValue !== null
			? {
					source:
						(integrationValue as { source?: unknown }).source === "connector" ||
						(integrationValue as { source?: unknown }).source === "mcp"
							? (integrationValue as { source: "connector" | "mcp" }).source
							: ("native" as const),
					key: asNonEmptyString((integrationValue as { key?: unknown }).key),
					name: asNonEmptyString((integrationValue as { name?: unknown }).name),
				}
			: undefined;
	const contextValue = metadata?.context;
	const context =
		typeof contextValue === "object" && contextValue !== null
			? {
					subagentType: asNonEmptyString((contextValue as { subagentType?: unknown }).subagentType),
					intent: asNonEmptyString((contextValue as { intent?: unknown }).intent) as
						| "inspect"
						| "author"
						| "verify"
						| "persist"
						| "discover_skill"
						| undefined,
					artifactType: asNonEmptyString((contextValue as { artifactType?: unknown }).artifactType),
					skillName: asNonEmptyString((contextValue as { skillName?: unknown }).skillName),
				}
			: undefined;
	const detailValue = metadata?.safeDetail;
	const safeDetail =
		typeof detailValue === "object" && detailValue !== null
			? {
					subject: asNonEmptyString((detailValue as { subject?: unknown }).subject),
					count: asFiniteNumber((detailValue as { count?: unknown }).count),
					domain: asNonEmptyString((detailValue as { domain?: unknown }).domain),
					filename: asNonEmptyString((detailValue as { filename?: unknown }).filename),
				}
			: undefined;
	return {
		startedAt: asNonEmptyString(metadata?.startedAt),
		completedAt: asNonEmptyString(metadata?.completedAt),
		activeTitle: asNonEmptyString(metadata?.activeTitle),
		completedTitle: asNonEmptyString(metadata?.completedTitle),
		integration,
		context,
		safeDetail,
	};
}

/**
 * True iff THIS tool-call is the actual interrupt request (carries an
 * ``action_requests[]``), not just a parent ``task`` wrapper that
 * inherited the propagated ``__interrupt__`` flag. Pending requests
 * are hidden so ``HitlApprovalCard`` owns the pending UX; the
 * ``length > 0`` guard keeps parent task wrappers visible so their
 * children stay indented under the delegation span.
 */
/**
 * Stable interrupt signal across pre/post decision: the resume flow
 * spreads the original result and only adds ``__decided__``, so
 * ``__interrupt__`` alone is the right key.
 */
function hasInterruptMarker(result: unknown): boolean {
	if (typeof result !== "object" || result === null) return false;
	return (result as { __interrupt__?: unknown }).__interrupt__ === true;
}

interface ToolCallSlim {
	toolName: string;
	toolCallId: string;
	result?: unknown;
	spanId?: string;
}

/**
 * During the live-resume window the in-memory message holds BOTH the
 * OLD interrupt-frame parts AND the freshly-streamed resume parts in
 * a new ``task`` scope. Without this filter we'd render both until
 * the next reload (where ``reconcileInterruptedAssistantMessages``
 * folds the OLD row into the resume row upstream).
 *
 * A tool-call is "interrupt-affected" when it either carries
 * ``__interrupt__`` directly or sits in a span that contains one. An
 * affected call is superseded iff a later same-name call in a
 * different scope exists. The conservative branch (no successor)
 * preserves rejects that ended the run with no replacement.
 */
function collectSupersededToolCallIds(content: readonly unknown[]): Set<string> {
	const slims: ToolCallSlim[] = [];
	for (const part of content) {
		if (!isToolCallPart(part)) continue;
		slims.push({
			toolName: part.toolName,
			toolCallId: part.toolCallId,
			result: part.result,
			spanId: asNonEmptyString(part.metadata?.spanId),
		});
	}

	const interruptedSpans = new Set<string>();
	for (const tc of slims) {
		if (!hasInterruptMarker(tc.result)) continue;
		if (tc.spanId) interruptedSpans.add(tc.spanId);
	}

	const superseded = new Set<string>();
	for (let i = 0; i < slims.length; i++) {
		const tc = slims[i];
		const inInterruptedSpan = tc.spanId !== undefined && interruptedSpans.has(tc.spanId);
		const isDirectInterrupt = hasInterruptMarker(tc.result);
		if (!inInterruptedSpan && !isDirectInterrupt) continue;

		for (let j = i + 1; j < slims.length; j++) {
			// Both-undefined counts as different scopes so standalone
			// HITL tools (no delegation) get caught.
			const sameSpan = tc.spanId !== undefined && slims[j].spanId === tc.spanId;
			if (slims[j].toolName === tc.toolName && !sameSpan) {
				superseded.add(tc.toolCallId);
				break;
			}
		}
	}

	return superseded;
}

/**
 * Coarse status for orphan tool-calls (no joined thinking step). The
 * per-tool body picks its own visual state from ``result``; this
 * only feeds the chrome dot/header.
 */
function deriveToolCallStatus(result: unknown): ItemStatus {
	if (!result) return "running";
	if (typeof result === "object" && result !== null) {
		const r = result as {
			__interrupt__?: unknown;
			__decided__?: unknown;
			error?: unknown;
			status?: unknown;
			state?: unknown;
		};
		if (r.__interrupt__ === true && r.__decided__ === "reject") return "cancelled";
		if (r.__interrupt__ === true && r.__decided__ === undefined) return "awaiting_approval";
		if (r.error || r.status === "error" || r.state === "error" || r.state === "aborted")
			return "error";
	}
	return "completed";
}

function mapStepStatus(status: ThinkingStepInput["status"]): ItemStatus {
	if (status === "in_progress") return "running";
	return status;
}

/**
 * Pure builder: thinking steps + message content → ``TimelineItem[]``.
 * Joins tool-calls to thinking steps via ``metadata.thinkingStepId``,
 * appends unjoined tool-calls as orphans, drops superseded
 * interrupt-frame parts and pending HITL requests (those are owned
 * by ``HitlApprovalCard``). ``result`` is forwarded verbatim so
 * per-tool bodies can discriminate.
 */
export function buildTimeline(
	thinkingSteps: readonly ThinkingStepInput[],
	content: readonly unknown[] | undefined
): TimelineItem[] {
	const toolByStepId = new Map<string, ToolCallPart>();
	const supersededStepIds = new Set<string>();
	const consumedToolCallIds = new Set<string>();
	const superseded = content ? collectSupersededToolCallIds(content) : new Set<string>();

	if (content) {
		for (const part of content) {
			if (!isToolCallPart(part)) continue;
			const tid = asNonEmptyString(part.metadata?.thinkingStepId);
			if (superseded.has(part.toolCallId)) {
				if (tid) supersededStepIds.add(tid);
				continue;
			}
			if (tid) toolByStepId.set(tid, part);
		}
	}

	const items: TimelineItem[] = [];

	for (const step of thinkingSteps) {
		// Drop the step alongside its superseded tool-call, otherwise
		// it'd render as an orphan reasoning row with the OLD title.
		if (supersededStepIds.has(step.id)) continue;

		const stepSpanId = asNonEmptyString(step.metadata?.spanId);
		const joined = toolByStepId.get(step.id);

		if (joined) {
			consumedToolCallIds.add(joined.toolCallId);
			const resultStatus = deriveToolCallStatus(joined.result);
			const item: ToolCallItem = {
				kind: "tool-call",
				id: step.id,
				status:
					resultStatus === "cancelled" || resultStatus === "error"
						? resultStatus
						: resultStatus === "awaiting_approval"
							? "awaiting_approval"
							: mapStepStatus(step.status),
				sequence: items.length,
				items: step.items.length > 0 ? step.items : undefined,
				spanId: stepSpanId ?? asNonEmptyString(joined.metadata?.spanId),
				...extractPresentationMetadata({ ...joined.metadata, ...step.metadata }),
				toolName: joined.toolName,
				toolCallId: joined.toolCallId,
				args: joined.args ?? {},
				argsText: joined.argsText,
				result: joined.result,
				langchainToolCallId: joined.langchainToolCallId,
				thinkingStepId: step.id,
			};
			items.push(item);
			continue;
		}

		const reasoning: ReasoningItem = {
			kind: "reasoning",
			id: step.id,
			status: mapStepStatus(step.status),
			sequence: items.length,
			items: step.items.length > 0 ? step.items : undefined,
			spanId: stepSpanId,
			...extractPresentationMetadata(step.metadata),
			title: step.title,
		};
		items.push(reasoning);
	}

	if (content) {
		for (const part of content) {
			if (!isToolCallPart(part)) continue;
			if (consumedToolCallIds.has(part.toolCallId)) continue;
			if (superseded.has(part.toolCallId)) continue;
			const orphan: ToolCallItem = {
				kind: "tool-call",
				id: part.toolCallId,
				status: deriveToolCallStatus(part.result),
				sequence: items.length,
				spanId: asNonEmptyString(part.metadata?.spanId),
				...extractPresentationMetadata(part.metadata),
				toolName: part.toolName,
				toolCallId: part.toolCallId,
				args: part.args ?? {},
				argsText: part.argsText,
				result: part.result,
				langchainToolCallId: part.langchainToolCallId,
			};
			items.push(orphan);
		}
	}

	return items;
}
