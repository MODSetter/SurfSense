import {
	differenceInDays,
	differenceInMinutes,
	format,
	isThisYear,
	isToday,
	isTomorrow,
} from "date-fns";

/**
 * Format a date string as a human-readable relative time
 * - < 1 min: "Just now"
 * - < 60 min: "15 minutes ago"
 * - < 24 hours: "21 hours ago"
 * - < 7 days: "2 days ago"
 * - Older this year: "Jan 15"
 * - Older: "Jan 15, 2026"
 */
export function formatRelativeDate(dateString: string): string {
	const date = new Date(dateString);
	const now = new Date();
	const minutesAgo = Math.max(0, differenceInMinutes(now, date));
	const hoursAgo = Math.floor(minutesAgo / 60);
	const daysAgo = Math.floor(hoursAgo / 24);

	if (minutesAgo < 1) return "Just now";
	if (minutesAgo < 60) return `${minutesAgo} minute${minutesAgo === 1 ? "" : "s"} ago`;
	if (hoursAgo < 24) return `${hoursAgo} hour${hoursAgo === 1 ? "" : "s"} ago`;
	if (daysAgo < 7) return `${daysAgo} day${daysAgo === 1 ? "" : "s"} ago`;
	if (isThisYear(date)) return format(date, "MMM d");
	return format(date, "MMM d, yyyy");
}

/**
 * Format a future date string as a human-readable countdown.
 * - < 1 min: "Any moment"
 * - < 60 min: "in 15m"
 * - Today: "Today, 2:30 PM"
 * - Tomorrow: "Tomorrow, 2:30 PM"
 * - < 7 days: "in 3d"
 * - This year: "May 30, 2:30 PM"
 * - Older: "Jan 15, 2027"
 *
 * Mirrors {@link formatRelativeDate} but for moments strictly after now.
 * Falls back to the past-relative formatter if the timestamp is not in
 * the future (defensive — guards against stale "next_fire_at" values).
 */
export function formatRelativeFutureDate(dateString: string): string {
	const date = new Date(dateString);
	const now = new Date();
	const minutesAhead = differenceInMinutes(date, now);
	const daysAhead = differenceInDays(date, now);

	if (minutesAhead <= 0) return formatRelativeDate(dateString);
	if (minutesAhead < 1) return "Any moment";
	if (minutesAhead < 60) return `in ${minutesAhead}m`;
	if (isToday(date)) return `Today, ${format(date, "h:mm a")}`;
	if (isTomorrow(date)) return `Tomorrow, ${format(date, "h:mm a")}`;
	if (daysAhead < 7) return `in ${daysAhead}d`;
	if (isThisYear(date)) return format(date, "MMM d, h:mm a");
	return format(date, "MMM d, yyyy");
}

/**
 * Format a thread's last-updated timestamp for the chats sidebars.
 * Example: "Mar 23, 2026 at 4:30 PM"
 */
export function formatThreadTimestamp(dateString: string): string {
	return format(new Date(dateString), "MMM d, yyyy 'at' h:mm a");
}

/**
 * Format a chat message timestamp for inline display under a bubble.
 * Locale-aware, 12-hour clock. Example: "Jul 13, 10:42 PM".
 */
export function formatMessageTimestamp(date: Date): string {
	return date.toLocaleDateString(undefined, {
		month: "short",
		day: "numeric",
		hour: "numeric",
		minute: "2-digit",
		hour12: true,
	});
}
