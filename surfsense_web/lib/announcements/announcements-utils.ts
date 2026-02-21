import type { Announcement } from "@/contracts/types/announcement.types";

/**
 * Returns true when the current time falls within the announcement's
 * [startTime, endTime] window. Returns false for invalid windows
 * (endTime before startTime) or when now is outside the range.
 */
export function isAnnouncementActive(announcement: Announcement, now = new Date()): boolean {
	const start = new Date(announcement.startTime).getTime();
	const end = new Date(announcement.endTime).getTime();

	if (Number.isNaN(start) || Number.isNaN(end) || end < start) return false;

	const nowMs = now.getTime();
	return nowMs >= start && nowMs <= end;
}

/**
 * Returns true when the announcement's audience matches the viewer context.
 * - `"all"` — visible to everyone
 * - `"users"` — visible only to authenticated users
 * - `"web_visitors"` — visible only to unauthenticated visitors
 */
export function announcementMatchesAudience(
	announcement: Announcement,
	isAuthenticated: boolean
): boolean {
	switch (announcement.audience) {
		case "all":
			return true;
		case "users":
			return isAuthenticated;
		case "web_visitors":
			return !isAuthenticated;
		default:
			return false;
	}
}

/**
 * Filter announcements to only those that are currently active and
 * targeted at the given audience.
 */
export function getActiveAnnouncements(
	announcements: Announcement[],
	isAuthenticated: boolean,
	now = new Date()
): Announcement[] {
	return announcements.filter(
		(a) => isAnnouncementActive(a, now) && announcementMatchesAudience(a, isAuthenticated)
	);
}

/**
 * Returns the number of milliseconds until the next announcement either
 * starts or expires. Returns `null` when there are no upcoming transitions.
 * Useful for scheduling re-renders so the UI updates automatically.
 */
export function msUntilNextTransition(
	announcements: Announcement[],
	now = new Date()
): number | null {
	const nowMs = now.getTime();
	let nearest: number | null = null;

	for (const a of announcements) {
		const start = new Date(a.startTime).getTime();
		const end = new Date(a.endTime).getTime();
		if (Number.isNaN(start) || Number.isNaN(end) || end < start) continue;

		for (const edge of [start, end]) {
			if (edge > nowMs) {
				const diff = edge - nowMs;
				if (nearest === null || diff < nearest) nearest = diff;
			}
		}
	}

	return nearest;
}
