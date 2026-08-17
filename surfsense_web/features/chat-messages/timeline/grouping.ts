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

export type StandaloneTurnHeaderPhase = "spellweaving" | "responded";

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

export function getTraceGroupPath(
	part: TracePartLike,
	bodyToolNames: ReadonlySet<string>
): readonly ["group-trace"] | readonly [] {
	if (
		part.type === "reasoning" ||
		(part.type === "tool-call" && !isBodyTool(part, bodyToolNames))
	) {
		return ["group-trace"];
	}
	return [];
}

export function getLastTraceIndex(
	parts: readonly TracePartLike[],
	bodyToolNames: ReadonlySet<string>,
	showReasoning: boolean
): number {
	for (let index = parts.length - 1; index >= 0; index -= 1) {
		const part = parts[index];
		if (part.type === "reasoning" && !showReasoning) continue;
		if (getTraceGroupPath(part, bodyToolNames).length > 0) return index;
	}
	return -1;
}

export function getStandaloneTurnHeaderPhase({
	parts,
	bodyToolNames,
	threadRunning,
	lastTraceIndex,
	timingStatus,
}: {
	parts: readonly TracePartLike[];
	bodyToolNames: ReadonlySet<string>;
	threadRunning: boolean;
	lastTraceIndex: number;
	timingStatus?: ActivityTimingData["status"];
}): StandaloneTurnHeaderPhase | null {
	if (lastTraceIndex >= 0) return null;
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
