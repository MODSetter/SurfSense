import {
	type ActivityData,
	type ActivityTimingData,
	parseActivityData,
	parseActivityTimingData,
} from "@/lib/chat/streaming-state";

/** Extract the one backend-owned journal. Tool calls and legacy steps are never inspected. */
export function buildActivityJournal(content: readonly unknown[]): {
	activities: ActivityData[];
	timing: ActivityTimingData | null;
} {
	const part = content.find((candidate) => {
		if (typeof candidate !== "object" || candidate === null) return false;
		const { type, name } = candidate as { type?: unknown; name?: unknown };
		return type === "data-activities" || (type === "data" && name === "activities");
	}) as { data?: { activities?: unknown[]; timing?: unknown } } | undefined;
	return {
		activities: Array.isArray(part?.data?.activities)
			? part.data.activities
					.map(parseActivityData)
					.filter((activity): activity is ActivityData => activity !== null)
					.toSorted((a, b) => a.sequence - b.sequence || a.id.localeCompare(b.id))
			: [],
		timing: parseActivityTimingData(part?.data?.timing),
	};
}
