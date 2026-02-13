/**
 * Announcement system types
 *
 * Frontend-only announcement system that supports:
 * - Multiple announcement categories (update, feature, maintenance, info)
 * - Important flag for toast notifications
 * - Read/dismissed state tracking via localStorage
 */

/** Announcement category */
export type AnnouncementCategory = "update" | "feature" | "maintenance" | "info";

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
	/** If true, the user will see a toast notification for this announcement */
	isImportant: boolean;
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
	/** IDs of announcements the user has explicitly dismissed */
	dismissedIds: string[];
}
