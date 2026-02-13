"use client";

import { useCallback, useMemo, useSyncExternalStore } from "react";
import type { Announcement, AnnouncementCategory } from "@/contracts/types/announcement.types";
import { announcements } from "@/lib/announcements/announcements-data";
import {
	dismissAnnouncement,
	getAnnouncementState,
	isAnnouncementDismissed,
	isAnnouncementRead,
	markAllAnnouncementsRead,
	markAnnouncementRead,
} from "@/lib/announcements/announcements-storage";

// ---------------------------------------------------------------------------
// External-store plumbing so React re-renders when localStorage changes
// ---------------------------------------------------------------------------

let stateVersion = 0;
const listeners = new Set<() => void>();

function subscribe(callback: () => void) {
	listeners.add(callback);
	return () => listeners.delete(callback);
}

function getSnapshot() {
	return stateVersion;
}

function getServerSnapshot() {
	return 0;
}

/** Bump the version so useSyncExternalStore triggers a re-render */
function notify() {
	stateVersion++;
	for (const listener of listeners) listener();
}

// ---------------------------------------------------------------------------
// Enriched announcement with read/dismissed state
// ---------------------------------------------------------------------------

export interface AnnouncementWithState extends Announcement {
	isRead: boolean;
	isDismissed: boolean;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

interface UseAnnouncementsOptions {
	/** Filter by category */
	category?: AnnouncementCategory;
	/** If true, include dismissed announcements (default: false) */
	includeDismissed?: boolean;
}

export function useAnnouncements(options: UseAnnouncementsOptions = {}) {
	const { category, includeDismissed = false } = options;

	// Subscribe to state changes (re-renders when localStorage state is bumped)
	useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);

	const enriched: AnnouncementWithState[] = useMemo(() => {
		let items = announcements.map((a) => ({
			...a,
			isRead: isAnnouncementRead(a.id),
			isDismissed: isAnnouncementDismissed(a.id),
		}));

		if (category) {
			items = items.filter((a) => a.category === category);
		}

		if (!includeDismissed) {
			items = items.filter((a) => !a.isDismissed);
		}

		// Sort by date descending (newest first)
		items.sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());

		return items;
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [category, includeDismissed, stateVersion]);

	const unreadCount = useMemo(
		() => enriched.filter((a) => !a.isRead && !a.isDismissed).length,
		[enriched]
	);

	const handleMarkRead = useCallback((id: string) => {
		markAnnouncementRead(id);
		notify();
	}, []);

	const handleMarkAllRead = useCallback(() => {
		const state = getAnnouncementState();
		const unreadIds = announcements.filter((a) => !state.readIds.includes(a.id)).map((a) => a.id);
		markAllAnnouncementsRead(unreadIds);
		notify();
	}, []);

	const handleDismiss = useCallback((id: string) => {
		dismissAnnouncement(id);
		markAnnouncementRead(id);
		notify();
	}, []);

	return {
		announcements: enriched,
		unreadCount,
		markRead: handleMarkRead,
		markAllRead: handleMarkAllRead,
		dismiss: handleDismiss,
	};
}
