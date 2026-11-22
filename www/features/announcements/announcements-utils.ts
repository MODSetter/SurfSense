import type { Announcement } from "@/features/announcements/announcement.types";

/**
 * The announcement's own page. Every announcement has one:
 * `features/announcements/announcements-content.test.ts` fails when a body is missing.
 */
export function announcementPath(id: string): string {
	return `/announcements/${id}`;
}

/**
 * Returns true when the announcement has been published (startTime has
 * passed), regardless of whether its visibility window has expired.
 * Used for archive views like the announcements page.
 */
export function isAnnouncementPublished(announcement: Announcement, now = new Date()): boolean {
	const start = new Date(announcement.startTime).getTime();
	if (Number.isNaN(start)) return false;
	return now.getTime() >= start;
}
