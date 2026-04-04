"use client";

import { useQuery } from "@rocicorp/zero/react";
import { useCallback, useEffect, useRef, useState } from "react";
import type { InboxItem, NotificationCategory } from "@/contracts/types/inbox.types";
import { notificationsApiService } from "@/lib/apis/notifications-api.service";
import { queries } from "@/zero/queries";

export type {
	InboxItem,
	InboxItemTypeEnum,
	NotificationCategory,
} from "@/contracts/types/inbox.types";

const INITIAL_PAGE_SIZE = 50;
const SCROLL_PAGE_SIZE = 30;
const SYNC_WINDOW_DAYS = 4;

const CATEGORY_TYPES: Record<NotificationCategory, string[]> = {
	comments: ["new_mention", "comment_reply"],
	status: [
		"connector_indexing",
		"connector_deletion",
		"document_processing",
		"page_limit_exceeded",
	],
};

function getSyncCutoffDate(): string {
	const cutoff = new Date();
	cutoff.setDate(cutoff.getDate() - SYNC_WINDOW_DAYS);
	cutoff.setUTCHours(0, 0, 0, 0);
	return cutoff.toISOString();
}

/**
 * Hook for managing inbox items with API-first architecture + Zero real-time deltas.
 *
 * Architecture:
 * 1. API is the PRIMARY data source — fetches first page on mount with category filter
 * 2. Zero provides REAL-TIME updates (new items, status changes, read state)
 * 3. Unread count = olderUnreadOffset + recent unread from Zero
 */
export function useInbox(
	userId: string | null,
	searchSpaceId: number | null,
	category: NotificationCategory,
	prefetchedUnread?: { total_unread: number; recent_unread: number } | null,
	prefetchedUnreadReady = true
) {
	const [inboxItems, setInboxItems] = useState<InboxItem[]>([]);
	const [loading, setLoading] = useState(true);
	const [loadingMore, setLoadingMore] = useState(false);
	const [hasMore, setHasMore] = useState(false);
	const [error, setError] = useState<Error | null>(null);
	const [unreadCount, setUnreadCount] = useState(0);

	const initialLoadDoneRef = useRef(false);
	const olderUnreadOffsetRef = useRef<number | null>(null);
	const apiUnreadTotalRef = useRef(0);

	const categoryTypes = CATEGORY_TYPES[category];

	// EFFECT 1: Fetch first page + unread count from API with category filter
	useEffect(() => {
		if (!userId || !searchSpaceId) return;
		if (!prefetchedUnreadReady) return;

		let cancelled = false;

		setLoading(true);
		setInboxItems([]);
		setHasMore(false);
		initialLoadDoneRef.current = false;
		olderUnreadOffsetRef.current = null;
		apiUnreadTotalRef.current = 0;

		const fetchInitialData = async () => {
			try {
				const notificationsPromise = notificationsApiService.getNotifications({
					queryParams: {
						search_space_id: searchSpaceId,
						category,
						limit: INITIAL_PAGE_SIZE,
					},
				});

				const unreadPromise = prefetchedUnread
					? Promise.resolve(prefetchedUnread)
					: notificationsApiService.getUnreadCount(searchSpaceId, undefined, category);

				const [notificationsResponse, unreadResponse] = await Promise.all([
					notificationsPromise,
					unreadPromise,
				]);

				if (cancelled) return;

				setInboxItems(notificationsResponse.items);
				setHasMore(notificationsResponse.has_more);
				setUnreadCount(unreadResponse.total_unread);
				apiUnreadTotalRef.current = unreadResponse.total_unread;
				setError(null);
				initialLoadDoneRef.current = true;
			} catch (err) {
				if (cancelled) return;
				console.error(`[useInbox:${category}] Initial load failed:`, err);
				setError(err instanceof Error ? err : new Error("Failed to load notifications"));
			} finally {
				if (!cancelled) setLoading(false);
			}
		};

		fetchInitialData();
		return () => {
			cancelled = true;
		};
	}, [userId, searchSpaceId, category, prefetchedUnread, prefetchedUnreadReady]);

	// EFFECT 2: Zero real-time sync for notification updates
	const [zeroNotifications] = useQuery(queries.notifications.byUser({ userId: userId ?? "" }));

	useEffect(() => {
		if (!userId || !searchSpaceId || !zeroNotifications || !initialLoadDoneRef.current) return;

		const cutoff = new Date(getSyncCutoffDate());

		const validItems = zeroNotifications.filter((item) => {
			if (item.id == null) return false;
			if (!categoryTypes.includes(item.type)) return false;
			if (item.searchSpaceId !== null && item.searchSpaceId !== searchSpaceId) return false;
			return true;
		});

		const recentItems = validItems.filter((item) => new Date(item.createdAt) > cutoff);

		const liveIds = new Set(recentItems.map((d) => d.id));

		setInboxItems((prev) => {
			const prevIds = new Set(prev.map((d) => d.id));

			const newItems: InboxItem[] = recentItems
				.filter((d) => !prevIds.has(d.id))
				.map(
					(item) =>
						({
							id: item.id,
							user_id: item.userId,
							search_space_id: item.searchSpaceId ?? undefined,
							type: item.type,
							title: item.title,
							message: item.message,
							read: item.read,
							metadata: item.metadata as unknown as Record<string, unknown>,
							created_at: new Date(item.createdAt).toISOString(),
							updated_at: item.updatedAt ? new Date(item.updatedAt).toISOString() : null,
						}) as InboxItem
				);

			const liveById = new Map(recentItems.map((v) => [v.id, v]));

			let updated = prev.map((existing) => {
				const liveItem = liveById.get(existing.id);
				if (liveItem) {
					return {
						...existing,
						read: liveItem.read,
						title: liveItem.title,
						message: liveItem.message,
						metadata: liveItem.metadata as unknown as Record<string, unknown>,
					} as InboxItem;
				}
				return existing;
			});

			updated = updated.filter((item) => {
				if (new Date(item.created_at) < cutoff) return true;
				return liveIds.has(item.id);
			});

			if (newItems.length > 0) {
				return [...newItems, ...updated];
			}

			return updated;
		});

		// Calibrate older-unread offset on first Zero data
		if (olderUnreadOffsetRef.current === null) {
			const recentUnreadCount = recentItems.filter((item) => !item.read).length;
			olderUnreadOffsetRef.current = Math.max(0, apiUnreadTotalRef.current - recentUnreadCount);
		}

		if (olderUnreadOffsetRef.current !== null) {
			const recentUnreadCount = recentItems.filter((item) => !item.read).length;
			setUnreadCount(olderUnreadOffsetRef.current + recentUnreadCount);
		}
	}, [userId, searchSpaceId, zeroNotifications, categoryTypes]);

	// Load more pages via API (cursor-based using before_date)
	const loadMore = useCallback(async () => {
		if (loadingMore || !hasMore || !userId || !searchSpaceId) return;

		setLoadingMore(true);
		try {
			const oldestItem = inboxItems.length > 0 ? inboxItems[inboxItems.length - 1] : null;
			const beforeDate = oldestItem?.created_at ?? undefined;

			const response = await notificationsApiService.getNotifications({
				queryParams: {
					search_space_id: searchSpaceId,
					category,
					before_date: beforeDate,
					limit: SCROLL_PAGE_SIZE,
				},
			});

			const newItems = response.items;

			setInboxItems((prev) => {
				const existingIds = new Set(prev.map((d) => d.id));
				const deduped = newItems.filter((d) => !existingIds.has(d.id));
				return [...prev, ...deduped];
			});
			setHasMore(response.has_more);
		} catch (err) {
			console.error(`[useInbox:${category}] Load more failed:`, err);
		} finally {
			setLoadingMore(false);
		}
	}, [loadingMore, hasMore, userId, searchSpaceId, inboxItems, category]);

	// Mark single item as read with optimistic update
	const markAsRead = useCallback(
		async (itemId: number) => {
			const item = inboxItems.find((i) => i.id === itemId);
			if (!item || item.read) return true;

			const cutoff = new Date(getSyncCutoffDate());
			const isOlderItem = new Date(item.created_at) < cutoff;

			setInboxItems((prev) => prev.map((i) => (i.id === itemId ? { ...i, read: true } : i)));
			setUnreadCount((prev) => Math.max(0, prev - 1));

			if (isOlderItem && olderUnreadOffsetRef.current !== null) {
				olderUnreadOffsetRef.current = Math.max(0, olderUnreadOffsetRef.current - 1);
			}

			try {
				const result = await notificationsApiService.markAsRead({ notificationId: itemId });
				if (!result.success) {
					setInboxItems((prev) => prev.map((i) => (i.id === itemId ? { ...i, read: false } : i)));
					setUnreadCount((prev) => prev + 1);
					if (isOlderItem && olderUnreadOffsetRef.current !== null) {
						olderUnreadOffsetRef.current += 1;
					}
				}
				return result.success;
			} catch (err) {
				console.error("Failed to mark as read:", err);
				setInboxItems((prev) => prev.map((i) => (i.id === itemId ? { ...i, read: false } : i)));
				setUnreadCount((prev) => prev + 1);
				if (isOlderItem && olderUnreadOffsetRef.current !== null) {
					olderUnreadOffsetRef.current += 1;
				}
				return false;
			}
		},
		[inboxItems]
	);

	// Mark all as read with optimistic update
	const markAllAsRead = useCallback(async () => {
		const prevItems = inboxItems;
		const prevCount = unreadCount;
		const prevOffset = olderUnreadOffsetRef.current;

		setInboxItems((prev) => prev.map((item) => ({ ...item, read: true })));
		setUnreadCount(0);
		olderUnreadOffsetRef.current = 0;

		try {
			const result = await notificationsApiService.markAllAsRead();
			if (!result.success) {
				setInboxItems(prevItems);
				setUnreadCount(prevCount);
				olderUnreadOffsetRef.current = prevOffset;
			}
			return result.success;
		} catch (err) {
			console.error("Failed to mark all as read:", err);
			setInboxItems(prevItems);
			setUnreadCount(prevCount);
			olderUnreadOffsetRef.current = prevOffset;
			return false;
		}
	}, [inboxItems, unreadCount]);

	return {
		inboxItems,
		unreadCount,
		markAsRead,
		markAllAsRead,
		loading,
		loadingMore,
		hasMore,
		loadMore,
		error,
	};
}
