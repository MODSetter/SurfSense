/**
 * Announcement system types
 *
 * Frontend-only announcement system that supports:
 * - Multiple announcement categories (update, feature, maintenance, info)
 * - Important flag for toast notifications
 * - Time-bound visibility (start/end times)
 * - Audience targeting (all, users, web_visitors)
 * - Read state tracking via localStorage
 */

/** Announcement category */
export type AnnouncementCategory = "update" | "feature" | "maintenance" | "info";

/** Who should see the announcement */
export type AnnouncementAudience = "all" | "users" | "web_visitors";

/** Single announcement entry */
export interface Announcement {
	/** Unique identifier */
	id: string;
	/** Short title */
	title: string;
	/** Full description (supports basic text) */
	description: string;
	/** Category for visual styling and filtering */
	category: AnnouncementCategory;
	/** ISO date string of when the announcement was published */
	date: string;
	/** ISO datetime — announcement becomes visible at this time */
	startTime: string;
	/** ISO datetime — announcement expires and is hidden after this time */
	endTime: string;
	/** Who should see this announcement */
	audience: AnnouncementAudience;
	/** If true, the user will see a toast notification for this announcement */
	isImportant: boolean;
	/**
	 * If true, this announcement is shown in a blocking spotlight dialog that the
	 * user must explicitly acknowledge ("Got it"). Until acknowledged it keeps
	 * reappearing; once acknowledged it never shows again. Spotlight announcements
	 * are skipped by the lightweight toast provider to avoid double notifications.
	 */
	spotlight?: boolean;
	/** Optional head/banner image shown at the top of the announcement */
	image?: {
		/** Image source (public path or absolute URL) */
		src: string;
		/** Accessible alt text */
		alt: string;
	};
	/** Optional CTA link */
	link?: {
		label: string;
		url: string;
	};
}

/** State stored in localStorage for tracking user interactions */
export interface AnnouncementUserState {
	/** IDs of announcements the user has read (clicked/viewed) */
	readIds: string[];
	/** IDs of important announcements already shown as toasts */
	toastedIds: string[];
}
