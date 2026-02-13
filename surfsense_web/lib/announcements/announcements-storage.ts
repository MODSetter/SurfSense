import type { AnnouncementUserState } from "@/contracts/types/announcement.types";

const STORAGE_KEY = "surfsense_announcements_state";

const defaultState: AnnouncementUserState = {
	readIds: [],
	toastedIds: [],
	dismissedIds: [],
};

/**
 * Get the current announcement user state from localStorage
 */
export function getAnnouncementState(): AnnouncementUserState {
	if (typeof window === "undefined") return defaultState;

	try {
		const raw = localStorage.getItem(STORAGE_KEY);
		if (!raw) return defaultState;
		const parsed = JSON.parse(raw) as Partial<AnnouncementUserState>;
		return {
			readIds: Array.isArray(parsed.readIds) ? parsed.readIds : [],
			toastedIds: Array.isArray(parsed.toastedIds) ? parsed.toastedIds : [],
			dismissedIds: Array.isArray(parsed.dismissedIds) ? parsed.dismissedIds : [],
		};
	} catch {
		return defaultState;
	}
}

/**
 * Save announcement user state to localStorage
 */
function saveAnnouncementState(state: AnnouncementUserState): void {
	if (typeof window === "undefined") return;
	try {
		localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
	} catch {
		// Silently fail if localStorage is full or unavailable
	}
}

/**
 * Mark an announcement as read
 */
export function markAnnouncementRead(id: string): void {
	const state = getAnnouncementState();
	if (!state.readIds.includes(id)) {
		state.readIds.push(id);
		saveAnnouncementState(state);
	}
}

/**
 * Mark all announcements as read
 */
export function markAllAnnouncementsRead(ids: string[]): void {
	const state = getAnnouncementState();
	const newIds = ids.filter((id) => !state.readIds.includes(id));
	if (newIds.length > 0) {
		state.readIds.push(...newIds);
		saveAnnouncementState(state);
	}
}

/**
 * Dismiss an announcement (hide it from the list)
 */
export function dismissAnnouncement(id: string): void {
	const state = getAnnouncementState();
	if (!state.dismissedIds.includes(id)) {
		state.dismissedIds.push(id);
		saveAnnouncementState(state);
	}
}

/**
 * Mark an important announcement as already toasted (shown as toast)
 */
export function markAnnouncementToasted(id: string): void {
	const state = getAnnouncementState();
	if (!state.toastedIds.includes(id)) {
		state.toastedIds.push(id);
		saveAnnouncementState(state);
	}
}

/**
 * Check if an announcement has been read
 */
export function isAnnouncementRead(id: string): boolean {
	return getAnnouncementState().readIds.includes(id);
}

/**
 * Check if an announcement has been toasted
 */
export function isAnnouncementToasted(id: string): boolean {
	return getAnnouncementState().toastedIds.includes(id);
}

/**
 * Check if an announcement has been dismissed
 */
export function isAnnouncementDismissed(id: string): boolean {
	return getAnnouncementState().dismissedIds.includes(id);
}
