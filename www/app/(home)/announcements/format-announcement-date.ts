/**
 * Announcement dates are UTC midnights, so they are printed in UTC: a server
 * west of Greenwich would otherwise show the day before.
 */
export function formatAnnouncementDate(date: string, month: "short" | "long" = "short"): string {
	return new Date(date).toLocaleDateString("en-US", {
		year: "numeric",
		month,
		day: "numeric",
		timeZone: "UTC",
	});
}
