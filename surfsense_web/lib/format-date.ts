import { differenceInDays, differenceInMinutes, format, isToday, isYesterday } from "date-fns";

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
