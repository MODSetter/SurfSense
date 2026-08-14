import {
	type ActivityData,
	type ActivityTimingData,
	parseActivityData,
	parseActivityTimingData,
} from "@/lib/chat/streaming-state";

export interface TracePartLike {
	type?: unknown;
	name?: unknown;
	data?: unknown;
	toolName?: unknown;
	toolCallId?: unknown;
	metadata?: unknown;
}

export interface ActivityJournal {
	byId: ReadonlyMap<string, ActivityData>;
	timing: ActivityTimingData | null;
}

function activitySnapshots(part: TracePartLike): {
	activities?: unknown;
	timing?: unknown;
} | null {
	if (part.type === "data-activities") {
		return typeof part.data === "object" && part.data !== null
			? (part.data as { activities?: unknown; timing?: unknown })
			: null;
	}
	if (part.type === "data" && part.name === "activities") {
		return typeof part.data === "object" && part.data !== null
			? (part.data as { activities?: unknown; timing?: unknown })
			: null;
	}
	return null;
}

/**
 * Build the canonical activity lookup. Duplicate snapshots are resolved by ID;
 * a terminal snapshot never regresses to a later non-terminal snapshot.
 */
export function buildActivityLookup(parts: readonly TracePartLike[]): ActivityJournal {
	const byId = new Map<string, ActivityData>();
	let timing: ActivityTimingData | null = null;
	for (const part of parts) {
		const journal = activitySnapshots(part);
		if (!journal) continue;
		if (Array.isArray(journal.activities)) {
			for (const candidate of journal.activities) {
				const activity = parseActivityData(candidate);
				if (!activity) continue;
				const current = byId.get(activity.id);
				const currentTerminal =
					current?.status === "completed" ||
					current?.status === "error" ||
					current?.status === "cancelled" ||
					current?.status === "interrupted";
				const nextTerminal =
					activity.status === "completed" ||
					activity.status === "error" ||
					activity.status === "cancelled" ||
					activity.status === "interrupted";
				if (!currentTerminal || nextTerminal) byId.set(activity.id, activity);
			}
		}
		timing = parseActivityTimingData(journal.timing) ?? timing;
	}
	return { byId, timing };
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

export type TraceRun =
	| { type: "trace"; indices: number[] }
	| { type: "text" | "body-tool" | "other"; index: number };

/** Pure mirror of GroupedParts adjacency, retained as the smallest regression check. */
export function groupTraceRuns(
	parts: readonly TracePartLike[],
	bodyToolNames: ReadonlySet<string>
): TraceRun[] {
	const result: TraceRun[] = [];
	for (let index = 0; index < parts.length; index += 1) {
		const part = parts[index];
		if (activitySnapshots(part)) continue;
		if (getTraceGroupPath(part, bodyToolNames).length > 0) {
			const previous = result.at(-1);
			if (previous?.type === "trace") previous.indices.push(index);
			else result.push({ type: "trace", indices: [index] });
			continue;
		}
		result.push({
			type: part.type === "text" ? "text" : isBodyTool(part, bodyToolNames) ? "body-tool" : "other",
			index,
		});
	}
	return result;
}
