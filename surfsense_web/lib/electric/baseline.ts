import type { MutableRefObject } from "react";

/**
 * Extract the newest `created_at` timestamp from a list of items.
 * Used to establish the server-clock cutoff for the baseline timing-gap check.
 *
 * Uses Date parsing instead of string comparison because the API (Python
 * isoformat: "+00:00" suffix) and Electric/PGlite ("Z" suffix, variable
 * fractional-second precision) produce different string formats.
 */
export function getNewestTimestamp<T extends { created_at: string }>(items: T[]): string | null {
	if (items.length === 0) return null;
	let newest = items[0].created_at;
	let newestMs = new Date(newest).getTime();
	for (let i = 1; i < items.length; i++) {
		const ms = new Date(items[i].created_at).getTime();
		if (ms > newestMs) {
			newest = items[i].created_at;
			newestMs = ms;
		}
	}
	return newest;
}

/**
 * Identify genuinely new items from an Electric live query callback.
 *
 * On Electric's first callback, ALL live IDs are snapshotted as the baseline.
 * Items beyond the API's first page are in this baseline and stay hidden
 * (they'll appear via scroll pagination). Items created in the timing gap
 * between the API fetch and Electric's first callback are rescued via the
 * `newestApiTimestamp` check — their `created_at` is newer than anything
 * the API returned, so they pass through.
 *
 */
export function filterNewElectricItems<T extends { id: number; created_at: string }>(
	validItems: T[],
	liveIds: Set<number>,
	prevIds: Set<number>,
	baselineRef: MutableRefObject<Set<number> | null>,
	newestApiTimestamp: string | null
): T[] {
	if (baselineRef.current === null) {
		baselineRef.current = new Set(liveIds);
	}

	const baseline = baselineRef.current;
	const cutoffMs = newestApiTimestamp ? new Date(newestApiTimestamp).getTime() : null;

	const newItems = validItems.filter((item) => {
		if (prevIds.has(item.id)) return false;
		if (!baseline.has(item.id)) return true;
		if (cutoffMs !== null && new Date(item.created_at).getTime() > cutoffMs) return true;
		return false;
	});

	for (const item of newItems) {
		baseline.add(item.id);
	}

	return newItems;
}
