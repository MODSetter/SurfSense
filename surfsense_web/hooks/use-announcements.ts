"use client";

import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import type { Announcement, AnnouncementCategory } from "@/contracts/types/announcement.types";
import { announcements } from "@/lib/announcements/announcements-data";
import {
	getAnnouncementState,
	isAnnouncementRead,
	markAllAnnouncementsRead,
	markAnnouncementRead,
} from "@/lib/announcements/announcements-storage";
import {
	getActiveAnnouncements,
	msUntilNextTransition,
} from "@/lib/announcements/announcements-utils";
import { isAuthenticated } from "@/lib/auth-utils";

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
// Enriched announcement with read state
// ---------------------------------------------------------------------------

export interface AnnouncementWithState extends Announcement {
	isRead: boolean;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

interface UseAnnouncementsOptions {
	/** Filter by category */
	category?: AnnouncementCategory;
}

export function useAnnouncements(options: UseAnnouncementsOptions = {}) {
	const { category } = options;

	// Subscribe to state changes (re-renders when localStorage state is bumped)
	useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);

	// Tick counter that increments when a start/end boundary is crossed,
	// so useMemo re-evaluates and expired announcements disappear.
	const [tick, setTick] = useState(0);

	const enriched: AnnouncementWithState[] = useMemo(() => {
		const authed = isAuthenticated();
		const now = new Date();
		let items: AnnouncementWithState[] = getActiveAnnouncements(announcements, authed, now).map(
			(a) => ({
				...a,
				isRead: isAnnouncementRead(a.id),
			})
		);

		if (category) {
			items = items.filter((a) => a.category === category);
		}

		items.sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());

		return items;
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [category, stateVersion, tick]);

	// Schedule a re-render when the next announcement starts or expires
	useEffect(() => {
		const ms = msUntilNextTransition(announcements);
		if (ms === null) return;

		// Cap at 60 s so we don't hold a very long timer; we'll re-check then.
		const delay = Math.min(ms + 500, 60_000);
		const id = setTimeout(() => setTick((t) => t + 1), delay);
		return () => clearTimeout(id);
	}, [tick]);

	const unreadCount = useMemo(() => enriched.filter((a) => !a.isRead).length, [enriched]);

	// Keep a ref so callbacks are stable and don't cause re-render loops
	const enrichedRef = useRef(enriched);
	enrichedRef.current = enriched;

	const handleMarkRead = useCallback((id: string) => {
		markAnnouncementRead(id);
		notify();
	}, []);

	const handleMarkAllRead = useCallback(() => {
		const state = getAnnouncementState();
		const activeIds = enrichedRef.current.map((a) => a.id);
		const unreadIds = activeIds.filter((id) => !state.readIds.includes(id));
		if (unreadIds.length === 0) return;
		markAllAnnouncementsRead(unreadIds);
		notify();
	}, []);

	return {
		announcements: enriched,
		unreadCount,
		markRead: handleMarkRead,
		markAllRead: handleMarkAllRead,
	};
}
