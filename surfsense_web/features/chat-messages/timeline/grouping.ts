import {
	type ActivityJournal,
	type ActivityTimingData,
	extractActivityJournal,
} from "@/lib/chat/activity-journal";

export interface TracePartLike {
	type?: unknown;
	data?: unknown;
	text?: unknown;
	code?: unknown;
	toolName?: unknown;
	toolCallId?: unknown;
	metadata?: unknown;
}

export type TurnHeaderPhase = "spellweaving" | "responded";

export const LIVE_TURN_SEGMENT_KEY = "live-turn-segment";

export type TurnRenderItem =
	| {
			kind: "segment";
			key: string;
			segmentId: string | null;
			indices: readonly number[];
			phase: TurnHeaderPhase | null;
			live: boolean;
	  }
	| {
			kind: "text" | "body-tool";
			key: string;
			index: number;
	  };

/**
 * Build the canonical activity lookup. Duplicate snapshots are resolved by ID;
 * a terminal snapshot never regresses to a later non-terminal snapshot.
 */
export function buildActivityLookup(parts: readonly TracePartLike[]): ActivityJournal {
	return extractActivityJournal(parts);
}

export function getToolActivityId(part: TracePartLike): string | null {
	if (part.type !== "tool-call" || typeof part.metadata !== "object" || part.metadata === null) {
		return null;
	}
	const activityId = (part.metadata as Record<string, unknown>).activityId;
	return typeof activityId === "string" && activityId.length > 0 ? activityId : null;
}

export function isBodyTool(part: TracePartLike, bodyToolNames: ReadonlySet<string>): boolean {
	return (
		part.type === "tool-call" &&
		typeof part.toolName === "string" &&
		bodyToolNames.has(part.toolName)
	);
}

function getNoTraceTurnHeaderPhase({
	parts,
	bodyToolNames,
	threadRunning,
	timingStatus,
}: {
	parts: readonly TracePartLike[];
	bodyToolNames: ReadonlySet<string>;
	threadRunning: boolean;
	timingStatus?: ActivityTimingData["status"];
}): TurnHeaderPhase | null {
	if (threadRunning) return "spellweaving";
	if (timingStatus !== "completed") return null;

	const failed = parts.some(
		(part) =>
			part.type === "status" &&
			(part.code === "error" || part.code === "cancelled" || part.code === "no_response")
	);
	if (failed) return null;

	const hasVisibleOutput = parts.some(
		(part) =>
			(part.type === "text" && typeof part.text === "string" && part.text.trim().length > 0) ||
			isBodyTool(part, bodyToolNames)
	);
	return hasVisibleOutput ? "responded" : null;
}

function traceSegmentId(parts: readonly TracePartLike[], firstIndex: number): string {
	const firstPart = parts[firstIndex];
	if (firstPart?.type === "tool-call" && typeof firstPart.toolCallId === "string") {
		return `trace:${firstPart.toolCallId}`;
	}
	return `trace:${firstIndex}`;
}

function partKey(part: TracePartLike, index: number): string {
	return part.type === "tool-call" && typeof part.toolCallId === "string"
		? `part:${part.toolCallId}`
		: `part:${index}`;
}

/**
 * Projects canonical wire parts into the single sibling list rendered by a turn.
 * The final trace (or the no-trace placeholder) owns one message-scoped live key,
 * allowing React to move that slot without remounting it.
 */
export function buildTurnRenderItems({
	parts,
	bodyToolNames,
	showReasoning,
	threadRunning,
	timingStatus,
}: {
	parts: readonly TracePartLike[];
	bodyToolNames: ReadonlySet<string>;
	showReasoning: boolean;
	threadRunning: boolean;
	timingStatus?: ActivityTimingData["status"];
}): readonly TurnRenderItem[] {
	const items: TurnRenderItem[] = [];
	let traceIndices: number[] = [];

	const flushTrace = () => {
		if (traceIndices.length === 0) return;
		const segmentId = traceSegmentId(parts, traceIndices[0]);
		items.push({
			kind: "segment",
			key: segmentId,
			segmentId,
			indices: traceIndices,
			phase: null,
			live: false,
		});
		traceIndices = [];
	};

	for (let index = 0; index < parts.length; index += 1) {
		const part = parts[index];
		const isTrace =
			(part.type === "reasoning" && showReasoning) ||
			(part.type === "tool-call" && !isBodyTool(part, bodyToolNames));
		if (isTrace) {
			traceIndices.push(index);
			continue;
		}

		flushTrace();
		if (part.type === "text") {
			items.push({ kind: "text", key: partKey(part, index), index });
		} else if (isBodyTool(part, bodyToolNames)) {
			items.push({ kind: "body-tool", key: partKey(part, index), index });
		}
	}
	flushTrace();

	const lastTraceItemIndex = items.findLastIndex((item) => item.kind === "segment");
	if (lastTraceItemIndex >= 0) {
		const lastTrace = items[lastTraceItemIndex];
		if (lastTrace.kind === "segment") {
			items[lastTraceItemIndex] = {
				...lastTrace,
				key: LIVE_TURN_SEGMENT_KEY,
				live: true,
			};
		}
		return items;
	}

	const phase = getNoTraceTurnHeaderPhase({
		parts,
		bodyToolNames,
		threadRunning,
		timingStatus,
	});
	if (phase) {
		items.unshift({
			kind: "segment",
			key: LIVE_TURN_SEGMENT_KEY,
			segmentId: null,
			indices: [],
			phase,
			live: true,
		});
	}
	return items;
}

/** First wire position for each canonical activity, used to suppress duplicate tool relays. */
export function firstToolIndexByActivityId(
	parts: readonly TracePartLike[]
): ReadonlyMap<string, number> {
	const result = new Map<string, number>();
	for (let index = 0; index < parts.length; index += 1) {
		const activityId = getToolActivityId(parts[index]);
		if (activityId && !result.has(activityId)) result.set(activityId, index);
	}
	return result;
}
