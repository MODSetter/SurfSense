import {
	differenceInDays,
	differenceInMinutes,
	format,
	isThisYear,
	isToday,
	isTomorrow,
	isYesterday,
} from "date-fns";

/**
 * Format a date string as a human-readable relative time
 * - < 1 min: "Just now"
 * - < 60 min: "15m ago"
 * - Today: "Today, 2:30 PM"
 * - Yesterday: "Yesterday, 2:30 PM"
 * - < 7 days: "3d ago"
 * - Older: "Jan 15, 2026"
 */
export function formatRelativeDate(dateString: string): string {
	const date = new Date(dateString);
	const now = new Date();
	const minutesAgo = differenceInMinutes(now, date);
	const daysAgo = differenceInDays(now, date);

	if (minutesAgo < 1) return "Just now";
	if (minutesAgo < 60) return `${minutesAgo}m ago`;
	if (isToday(date)) return `Today, ${format(date, "h:mm a")}`;
	if (isYesterday(date)) return `Yesterday, ${format(date, "h:mm a")}`;
	if (daysAgo < 7) return `${daysAgo}d ago`;
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
