import type { ActivityData } from "@/lib/chat/streaming-state";

function latest(
	activities: readonly ActivityData[],
	predicate: (activity: ActivityData) => boolean
): ActivityData | undefined {
	let match: ActivityData | undefined;
	for (const activity of activities) {
		if (predicate(activity) && (!match || activity.sequence > match.sequence)) match = activity;
	}
	return match;
}

export function buildCompletionSummary(activities: readonly ActivityData[]): string {
	return (
		latest(
			activities,
			(activity) =>
				activity.status === "completed" ||
				activity.status === "error" ||
				activity.status === "cancelled" ||
				activity.status === "interrupted"
		)?.title ?? "Completed the work"
	);
}

export function buildActiveSummary(activities: readonly ActivityData[]): string {
	return (
		latest(
			activities,
			(activity) => activity.status === "running" || activity.status === "awaiting_approval"
		)?.title ??
		latest(activities, () => true)?.title ??
		"Spellweaving"
	);
}
