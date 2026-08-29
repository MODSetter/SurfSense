export type ActivityStatus =
	| "running"
	| "awaiting_approval"
	| "completed"
	| "error"
	| "cancelled"
	| "interrupted";

export interface ActivityTimingData {
	status: "running" | "paused" | "completed";
	activeDurationMs: number;
}

/** Client-only projection anchor. Never sent to or persisted by the backend. */
export interface ActivityTimingProjection {
	baseDurationMs: number;
	receivedAtPerformanceMs: number;
}

export interface ActivityData {
	id: string;
	sequence: number;
	kind: string;
	status: ActivityStatus;
	title: string;
	category: "file" | "research" | "artifact" | "connector" | "action";
	iconKey: string;
	progressTitle?: string;
	startedAt: string;
	completedAt?: string;
	integration?: {
		source: "native" | "connector" | "mcp";
		key?: string;
		name?: string;
	};
}

export interface ActivityJournalData {
	activities: ActivityData[];
	timing?: ActivityTimingData;
	timingProjection?: ActivityTimingProjection;
}

export interface ActivityJournalPart {
	type: "data-activities";
	data: ActivityJournalData;
}

export interface ActivityJournal {
	byId: ReadonlyMap<string, ActivityData>;
	timing: ActivityTimingData | null;
	timingProjection: ActivityTimingProjection | null;
}

const ACTIVITY_STATUSES = new Set<ActivityStatus>([
	"running",
	"awaiting_approval",
	"completed",
	"error",
	"cancelled",
	"interrupted",
]);
const ACTIVITY_CATEGORIES = new Set<ActivityData["category"]>([
	"file",
	"research",
	"artifact",
	"connector",
	"action",
]);
const TERMINAL_ACTIVITY_STATUSES = new Set<ActivityStatus>([
	"completed",
	"error",
	"cancelled",
	"interrupted",
]);

function nonEmptyString(value: unknown): value is string {
	return typeof value === "string" && value.trim().length > 0;
}

export function isTerminalActivityStatus(status: ActivityStatus): boolean {
	return TERMINAL_ACTIVITY_STATUSES.has(status);
}

export function compareActivities(a: ActivityData, b: ActivityData): number {
	if (a.sequence !== b.sequence) return a.sequence - b.sequence;
	if (a.id === b.id) return 0;
	return a.id < b.id ? -1 : 1;
}

export function sortActivities(activities: Iterable<ActivityData>): ActivityData[] {
	return [...activities].sort(compareActivities);
}

export function parseActivityData(value: unknown): ActivityData | null {
	if (typeof value !== "object" || value === null) return null;
	const activity = value as Record<string, unknown>;
	if (
		!nonEmptyString(activity.id) ||
		!Number.isSafeInteger(activity.sequence) ||
		(activity.sequence as number) < 0 ||
		!nonEmptyString(activity.kind) ||
		!ACTIVITY_STATUSES.has(activity.status as ActivityStatus) ||
		!nonEmptyString(activity.title) ||
		!ACTIVITY_CATEGORIES.has(activity.category as ActivityData["category"]) ||
		!nonEmptyString(activity.iconKey) ||
		!nonEmptyString(activity.startedAt)
	) {
		return null;
	}
	if (activity.progressTitle !== undefined && !nonEmptyString(activity.progressTitle)) {
		return null;
	}
	const terminal = isTerminalActivityStatus(activity.status as ActivityStatus);
	if (terminal !== nonEmptyString(activity.completedAt)) return null;

	let integration: ActivityData["integration"];
	if (activity.integration !== undefined) {
		if (typeof activity.integration !== "object" || activity.integration === null) return null;
		const candidate = activity.integration as Record<string, unknown>;
		if (
			candidate.source !== "native" &&
			candidate.source !== "connector" &&
			candidate.source !== "mcp"
		) {
			return null;
		}
		if (candidate.key !== undefined && !nonEmptyString(candidate.key)) return null;
		if (candidate.name !== undefined && !nonEmptyString(candidate.name)) return null;
		integration = {
			source: candidate.source,
			...(candidate.key ? { key: candidate.key as string } : {}),
			...(candidate.name ? { name: candidate.name as string } : {}),
		};
	}

	return {
		id: activity.id,
		sequence: activity.sequence as number,
		kind: activity.kind,
		status: activity.status as ActivityStatus,
		title: activity.title,
		category: activity.category as ActivityData["category"],
		iconKey: activity.iconKey,
		...(activity.progressTitle ? { progressTitle: activity.progressTitle as string } : {}),
		startedAt: activity.startedAt,
		...(activity.completedAt ? { completedAt: activity.completedAt as string } : {}),
		...(integration ? { integration } : {}),
	};
}

export function parseActivityTimingData(value: unknown): ActivityTimingData | null {
	if (typeof value !== "object" || value === null) return null;
	const timing = value as Record<string, unknown>;
	if (
		(timing.status !== "running" && timing.status !== "paused" && timing.status !== "completed") ||
		!Number.isSafeInteger(timing.activeDurationMs) ||
		(timing.activeDurationMs as number) < 0
	) {
		return null;
	}
	return {
		status: timing.status,
		activeDurationMs: timing.activeDurationMs as number,
	};
}

export function parseActivityTimingProjection(value: unknown): ActivityTimingProjection | null {
	if (typeof value !== "object" || value === null) return null;
	const projection = value as Record<string, unknown>;
	if (
		!Number.isSafeInteger(projection.baseDurationMs) ||
		(projection.baseDurationMs as number) < 0 ||
		!Number.isFinite(projection.receivedAtPerformanceMs) ||
		(projection.receivedAtPerformanceMs as number) < 0
	) {
		return null;
	}
	return {
		baseDurationMs: projection.baseDurationMs as number,
		receivedAtPerformanceMs: projection.receivedAtPerformanceMs as number,
	};
}

function hasSameIdentity(current: ActivityData, next: ActivityData): boolean {
	return (
		current.sequence === next.sequence &&
		current.kind === next.kind &&
		current.category === next.category &&
		current.iconKey === next.iconKey &&
		current.startedAt === next.startedAt
	);
}

/** Merge one validated snapshot without allowing identity changes or terminal regression. */
export function mergeActivity(
	current: ActivityData | undefined,
	value: unknown
): ActivityData | null {
	const next = parseActivityData(value);
	if (!next) return null;
	if (current && (!hasSameIdentity(current, next) || isTerminalActivityStatus(current.status))) {
		return current;
	}
	return next;
}

export function mergeActivityTiming(
	current: ActivityTimingData | null | undefined,
	value: unknown
): ActivityTimingData | null {
	const next = parseActivityTimingData(value);
	if (!next) return current ?? null;
	if (
		current?.status === "completed" ||
		(current && next.activeDurationMs < current.activeDurationMs)
	)
		return current;
	return next;
}

/**
 * Parse the canonical persisted leaf and assistant-ui's normalized runtime
 * representation of that same leaf.
 */
export function parseActivityJournalPart(value: unknown): ActivityJournalData | null {
	if (typeof value !== "object" || value === null) return null;
	const part = value as { type?: unknown; name?: unknown; data?: unknown };
	const isCanonicalPart = part.type === "data-activities";
	const isNormalizedPart = part.type === "data" && part.name === "activities";
	if (
		(!isCanonicalPart && !isNormalizedPart) ||
		typeof part.data !== "object" ||
		part.data === null
	) {
		return null;
	}
	const data = part.data as {
		activities?: unknown;
		timing?: unknown;
		timingProjection?: unknown;
	};
	if (!Array.isArray(data.activities)) return null;
	const byId = new Map<string, ActivityData>();
	for (const candidate of data.activities) {
		const parsed = parseActivityData(candidate);
		if (!parsed) continue;
		const merged = mergeActivity(byId.get(parsed.id), parsed);
		if (merged) byId.set(merged.id, merged);
	}
	const timing = parseActivityTimingData(data.timing);
	const timingProjection =
		timing?.status === "running" ? parseActivityTimingProjection(data.timingProjection) : null;
	return {
		activities: sortActivities(byId.values()),
		...(timing ? { timing } : {}),
		...(timingProjection ? { timingProjection } : {}),
	};
}

/** Extract and merge every canonical journal leaf in wire order. */
export function extractActivityJournal(parts: readonly unknown[]): ActivityJournal {
	const byId = new Map<string, ActivityData>();
	let timing: ActivityTimingData | null = null;
	let timingProjection: ActivityTimingProjection | null = null;
	for (const part of parts) {
		const journal = parseActivityJournalPart(part);
		if (!journal) continue;
		for (const candidate of journal.activities) {
			const merged = mergeActivity(byId.get(candidate.id), candidate);
			if (merged) byId.set(merged.id, merged);
		}
		const mergedTiming = mergeActivityTiming(timing, journal.timing);
		if (mergedTiming !== timing) {
			timing = mergedTiming;
			timingProjection = timing?.status === "running" ? (journal.timingProjection ?? null) : null;
		}
	}
	return {
		byId: new Map(sortActivities(byId.values()).map((activity) => [activity.id, activity])),
		timing,
		timingProjection,
	};
}

export function createActivityJournalPart(
	activities: Iterable<ActivityData>,
	timing?: ActivityTimingData | null,
	timingProjection?: ActivityTimingProjection | null
): ActivityJournalPart {
	return {
		type: "data-activities",
		data: {
			activities: sortActivities(activities),
			...(timing ? { timing } : {}),
			...(timing?.status === "running" && timingProjection ? { timingProjection } : {}),
		},
	};
}
