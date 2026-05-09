import type { ItemStatus, ReasoningItem, TimelineItem, ToolCallItem } from "./types";

/**
 * The thinking-step shape produced by the streaming pipeline (see
 * ``data-thinking-step`` SSE events). Kept structural here so this
 * builder doesn't depend on the legacy ``thinking-steps.tsx`` file.
 */
export interface ThinkingStepInput {
	id: string;
	title: string;
	items: string[];
	status: "pending" | "in_progress" | "completed";
	metadata?: Record<string, unknown>;
}

/**
 * The minimum tool-call-part shape we read from message content. We
 * accept ``unknown[]`` and structurally narrow per part — the assistant-
 * ui content type has many shapes, but only ``tool-call`` parts matter
 * here.
 */
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

/**
 * Derive coarse status for a tool-call from its result shape. Used
 * when the tool-call has no joined thinking step (orphan path).
 *
 * - HITL ``__decided__: "reject"``  → ``cancelled``
 * - Has any result                  → ``completed``
 * - No result yet                   → ``running``
 *
 * The per-tool component picks its own visual state from the result;
 * this is only the timeline chrome's coarse signal.
 */
function deriveToolCallStatus(result: unknown): ItemStatus {
	if (!result) return "running";
	if (typeof result === "object" && result !== null) {
		const r = result as { __interrupt__?: unknown; __decided__?: unknown };
		if (r.__interrupt__ === true && r.__decided__ === "reject") return "cancelled";
	}
	return "completed";
}

function mapStepStatus(status: ThinkingStepInput["status"]): ItemStatus {
	if (status === "in_progress") return "running";
	return status;
}

/**
 * True when a tool-call's result carries an HITL interrupt. Catches
 * both pre-decision (``__interrupt__: true``) and post-decision
 * (``__interrupt__: true, __decided__: …``) states — the resume
 * flow's decision-application spreads the original result and only
 * adds ``__decided__``, so ``__interrupt__`` alone is the stable
 * signal.
 */
function isInterruptInResult(result: unknown): boolean {
	if (typeof result !== "object" || result === null) return false;
	return (result as { __interrupt__?: unknown }).__interrupt__ === true;
}

/**
 * Build the set of tool-call ids that have been superseded by the
 * resume stream's continuation.
 *
 * The challenge: during the live resume window, the in-memory message
 * holds BOTH the rehydrated interrupt-frame parts (the OLD ``task`` +
 * its inner ``update_notion_page`` whose result has ``__decided__``)
 * AND the freshly-streamed resume parts (a NEW ``task`` + a NEW
 * ``update_notion_page`` with the actual success result). We need to
 * drop the entire OLD delegation chain so only the NEW one renders.
 *
 * Two-stage detection:
 *
 * 1. **Identify "interrupted spans"** — any spanId that contains at
 *    least one tool-call whose ``result.__interrupt__`` is true. This
 *    captures both the inner decided tool and its outer ``task``
 *    wrapper (which itself has no result but shares the spanId).
 *    Without this the wrapper survives as an orphan parent — the
 *    stray "Notion" row we saw post-approve.
 *
 * 2. **Mark a tool-call as superseded** when (a) it sits in an
 *    interrupted span OR carries the interrupt marker directly, AND
 *    (b) a later tool-call with the same ``toolName`` in a DIFFERENT
 *    span exists. The "different span" guard prevents self-supersession
 *    within the same delegation episode.
 *
 * Mirrors the message-level rule in
 * ``filterSupersededAbortedMessages`` but at the part level — same
 * data-shape problem (interrupt frame + resume continuation cohabiting
 * one in-memory message) one level down.
 *
 * Conservative: an interrupted tool-call with NO later same-named
 * different-span successor stays (e.g. a reject that ended the run, a
 * never-resumed decision).
 */
function collectSupersededToolCallIds(content: readonly unknown[]): Set<string> {
	const toolCallParts: ToolCallPart[] = [];
	for (const part of content) {
		if (isToolCallPart(part)) toolCallParts.push(part);
	}

	const interruptedSpans = new Set<string>();
	for (const part of toolCallParts) {
		if (!isInterruptInResult(part.result)) continue;
		const sid = asNonEmptyString(part.metadata?.spanId);
		if (sid) interruptedSpans.add(sid);
	}

	const superseded = new Set<string>();
	for (let i = 0; i < toolCallParts.length; i++) {
		const part = toolCallParts[i];
		const sid = asNonEmptyString(part.metadata?.spanId);
		const inInterruptedSpan = sid !== undefined && interruptedSpans.has(sid);
		const isDirectInterrupt = isInterruptInResult(part.result);
		if (!inInterruptedSpan && !isDirectInterrupt) continue;

		for (let j = i + 1; j < toolCallParts.length; j++) {
			const jsid = asNonEmptyString(toolCallParts[j].metadata?.spanId);
			// Both-undefined counts as "different scopes" so standalone
			// HITL tools (no delegation, no spanId) get caught. Naive
			// ``jsid !== sid`` misses them since ``undefined !==
			// undefined`` is false.
			const sameSpan = sid !== undefined && jsid === sid;
			if (toolCallParts[j].toolName === part.toolName && !sameSpan) {
				superseded.add(part.toolCallId);
				break;
			}
		}
	}

	return superseded;
}

/**
 * Build the timeline's flat ``TimelineItem[]`` from thinking steps +
 * message content tool-calls.
 *
 * 1. Index tool-call parts by ``metadata.thinkingStepId`` (O(1) join).
 * 2. Walk thinking steps in order. Joined → ``ToolCallItem``;
 *    unjoined → ``ReasoningItem``.
 * 3. Append unjoined tool-calls as orphan ``ToolCallItem``s (legacy
 *    history pre-``thinkingStepId``).
 *
 * Pure: no React, no I/O. ``result`` is forwarded verbatim — per-tool
 * components own its discrimination. ``isThreadRunning`` lives in
 * ``timeline.tsx`` as a runtime override.
 */
export function buildTimeline(
	thinkingSteps: readonly ThinkingStepInput[],
	content: readonly unknown[] | undefined
): TimelineItem[] {
	const toolByStepId = new Map<string, ToolCallPart>();
	const consumedToolCallIds = new Set<string>();
	const supersededToolCallIds = content
		? collectSupersededToolCallIds(content)
		: new Set<string>();

	if (content) {
		for (const part of content) {
			if (!isToolCallPart(part)) continue;
			const tid = asNonEmptyString(part.metadata?.thinkingStepId);
			if (tid) toolByStepId.set(tid, part);
		}
	}

	const items: TimelineItem[] = [];

	for (const step of thinkingSteps) {
		const stepSpanId = asNonEmptyString(step.metadata?.spanId);
		const joined = toolByStepId.get(step.id);

		// Drop the step entirely when it joins a superseded tool-call:
		// the resume stream has emitted a fresh same-named tool-call
		// (with its own thinking step) that takes over the row.
		// Without this, the timeline shows two "Notion → Update
		// Notion page" groups during the live resume window.
		if (joined && supersededToolCallIds.has(joined.toolCallId)) {
			consumedToolCallIds.add(joined.toolCallId);
			continue;
		}

		if (joined) {
			consumedToolCallIds.add(joined.toolCallId);
			const item: ToolCallItem = {
				kind: "tool-call",
				id: step.id,
				status: mapStepStatus(step.status),
				items: step.items.length > 0 ? step.items : undefined,
				spanId: stepSpanId ?? asNonEmptyString(joined.metadata?.spanId),
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
			items: step.items.length > 0 ? step.items : undefined,
			spanId: stepSpanId,
			title: step.title,
		};
		items.push(reasoning);
	}

	if (content) {
		for (const part of content) {
			if (!isToolCallPart(part)) continue;
			if (consumedToolCallIds.has(part.toolCallId)) continue;
			if (supersededToolCallIds.has(part.toolCallId)) continue;
			const orphan: ToolCallItem = {
				kind: "tool-call",
				id: part.toolCallId,
				status: deriveToolCallStatus(part.result),
				spanId: asNonEmptyString(part.metadata?.spanId),
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
