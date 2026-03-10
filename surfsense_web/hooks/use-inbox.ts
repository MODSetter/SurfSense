"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { InboxItem, NotificationCategory } from "@/contracts/types/inbox.types";
import { notificationsApiService } from "@/lib/apis/notifications-api.service";
import { filterNewElectricItems, getNewestTimestamp } from "@/lib/electric/baseline";
import { useElectricClient } from "@/lib/electric/context";

export type {
	InboxItem,
	InboxItemTypeEnum,
	NotificationCategory,
} from "@/contracts/types/inbox.types";

const INITIAL_PAGE_SIZE = 50;
const SCROLL_PAGE_SIZE = 30;
const SYNC_WINDOW_DAYS = 4;

const CATEGORY_TYPE_SQL: Record<NotificationCategory, string> = {
	comments: "AND type IN ('new_mention', 'comment_reply')",
	status:
		"AND type IN ('connector_indexing', 'connector_deletion', 'document_processing', 'page_limit_exceeded')",
};

/**
 * Calculate the cutoff date for sync window.
 * Rounds to the start of the day (midnight UTC) to ensure stable values
 * across re-renders.
 */
function getSyncCutoffDate(): string {
	const cutoff = new Date();
	cutoff.setDate(cutoff.getDate() - SYNC_WINDOW_DAYS);
	cutoff.setUTCHours(0, 0, 0, 0);
	return cutoff.toISOString();
}

/**
 * Hook for managing inbox items with API-first architecture + Electric real-time deltas.
 *
 * Architecture (Documents pattern, per-tab):
 * 1. API is the PRIMARY data source — fetches first page on mount with category filter
 * 2. Electric provides REAL-TIME updates (new items, status changes, read state)
 * 3. Baseline pattern prevents duplicates between API and Electric
 * 4. Electric sync shape is SHARED across instances (client-level caching)
 *    — each instance creates its own type-filtered live queries
 *
 * Unread count strategy:
 * - API provides the category-filtered total on mount (ground truth across all time)
 * - Electric live query counts unread within SYNC_WINDOW_DAYS (filtered by type)
 * - olderUnreadOffsetRef bridges the gap: total = offset + recent
 * - Optimistic updates adjust both the count and the offset (for old items)
 *
 * @param userId - The user ID to fetch inbox items for
 * @param searchSpaceId - The search space ID to filter inbox items
 * @param category - Which tab: "comments" or "status"
 */
export function useInbox(
	userId: string | null,
	searchSpaceId: number | null,
	category: NotificationCategory,
	prefetchedUnread?: { total_unread: number; recent_unread: number } | null,
	prefetchedUnreadReady = true,
) {
	const electricClient = useElectricClient();

	const [inboxItems, setInboxItems] = useState<InboxItem[]>([]);
	const [loading, setLoading] = useState(true);
	const [loadingMore, setLoadingMore] = useState(false);
	const [hasMore, setHasMore] = useState(false);
	const [error, setError] = useState<Error | null>(null);
	const [unreadCount, setUnreadCount] = useState(0);

	const initialLoadDoneRef = useRef(false);
	const electricBaselineIdsRef = useRef<Set<number> | null>(null);
	const newestApiTimestampRef = useRef<string | null>(null);
	const liveQueryRef = useRef<{ unsubscribe?: () => void } | null>(null);
	const unreadLiveQueryRef = useRef<{ unsubscribe?: () => void } | null>(null);

	const olderUnreadOffsetRef = useRef<number | null>(null);
	const apiUnreadTotalRef = useRef(0);

	// EFFECT 1: Fetch first page + unread count from API with category filter.
	// When prefetchedUnreadReady=false, we wait for the batch query to settle
	// before deciding whether we need an individual unread-count fallback call.
	useEffect(() => {
		if (!userId || !searchSpaceId) return;
		if (!prefetchedUnreadReady) return;

		let cancelled = false;

		setLoading(true);
		setInboxItems([]);
		setHasMore(false);
		initialLoadDoneRef.current = false;
		electricBaselineIdsRef.current = null;
		newestApiTimestampRef.current = null;
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

				// Use prefetched counts when available, otherwise fetch individually.
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
				newestApiTimestampRef.current = getNewestTimestamp(notificationsResponse.items);
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

	// EFFECT 2: Electric sync (shared shape) + per-instance type-filtered live queries
	useEffect(() => {
		if (!userId || !searchSpaceId || !electricClient) return;

		const uid = userId;
		const spaceId = searchSpaceId;
		const client = electricClient;
		const typeFilter = CATEGORY_TYPE_SQL[category];
		let mounted = true;

		async function setupElectricRealtime() {
			// Clean up previous live queries (NOT the sync shape — it's shared)
			if (liveQueryRef.current) {
				try {
					liveQueryRef.current.unsubscribe?.();
				} catch {
					/* PGlite may be closed */
				}
				liveQueryRef.current = null;
			}
			if (unreadLiveQueryRef.current) {
				try {
					unreadLiveQueryRef.current.unsubscribe?.();
				} catch {
					/* PGlite may be closed */
				}
				unreadLiveQueryRef.current = null;
			}

			try {
				const cutoffDate = getSyncCutoffDate();

				// Sync shape is cached by the Electric client — multiple hook instances
				// calling syncShape with the same params get the same handle.
				const handle = await client.syncShape({
					table: "notifications",
					where: `user_id = '${uid}' AND created_at > '${cutoffDate}'`,
					primaryKey: ["id"],
				});

				if (!mounted) return;

				if (!handle.isUpToDate && handle.initialSyncPromise) {
					await Promise.race([
						handle.initialSyncPromise,
						new Promise((resolve) => setTimeout(resolve, 5000)),
					]);
				}

				if (!mounted) return;

				const db = client.db as {
					live?: {
						query: <T>(
							sql: string,
							params?: (number | string)[]
						) => Promise<{
							subscribe: (cb: (result: { rows: T[] }) => void) => void;
							unsubscribe?: () => void;
						}>;
					};
				};

				if (!db.live?.query) return;

				// Per-instance live query filtered by category types
				const itemsQuery = `SELECT * FROM notifications 
					WHERE user_id = $1 
					AND (search_space_id = $2 OR search_space_id IS NULL)
					AND created_at > '${cutoffDate}'
					${typeFilter}
					ORDER BY created_at DESC`;

				const liveQuery = await db.live.query<InboxItem>(itemsQuery, [uid, spaceId]);

				if (!mounted) {
					liveQuery.unsubscribe?.();
					return;
				}

				liveQuery.subscribe((result: { rows: InboxItem[] }) => {
					if (!mounted || !result.rows || !initialLoadDoneRef.current) return;

					const validItems = result.rows.filter((item) => item.id != null && item.title != null);
					const cutoff = new Date(getSyncCutoffDate());

					const liveItemMap = new Map(validItems.map((d) => [d.id, d]));
					const liveIds = new Set(liveItemMap.keys());

					setInboxItems((prev) => {
						const prevIds = new Set(prev.map((d) => d.id));

						const newItems = filterNewElectricItems(
							validItems,
							liveIds,
							prevIds,
							electricBaselineIdsRef,
							newestApiTimestampRef.current
						);

						let updated = prev.map((item) => {
							const liveItem = liveItemMap.get(item.id);
							if (liveItem) return liveItem;
							return item;
						});

						const isFullySynced = handle.isUpToDate;
						if (isFullySynced) {
							updated = updated.filter((item) => {
								if (new Date(item.created_at) < cutoff) return true;
								return liveIds.has(item.id);
							});
						}

						if (newItems.length > 0) {
							return [...newItems, ...updated];
						}

						return updated;
					});

					// Calibrate the older-unread offset using baseline items
					// (items present in both Electric and the API-loaded list).
					// This avoids the timing bug where new items arriving between
					// the API fetch and Electric's first callback would be absorbed
					// into the offset, making the count appear unchanged.
					const baseline = electricBaselineIdsRef.current;
					if (olderUnreadOffsetRef.current === null && baseline !== null) {
						const baselineUnreadCount = validItems.filter(
							(item) => baseline.has(item.id) && !item.read
						).length;
						olderUnreadOffsetRef.current = Math.max(
							0,
							apiUnreadTotalRef.current - baselineUnreadCount
						);
					}

					// Derive unread count from all Electric items + the older offset
					if (olderUnreadOffsetRef.current !== null) {
						const electricUnreadCount = validItems.filter((item) => !item.read).length;
						setUnreadCount(olderUnreadOffsetRef.current + electricUnreadCount);
					}
				});

				liveQueryRef.current = liveQuery;

				// Per-instance unread count live query filtered by category types.
				// Acts as a secondary reactive path for read-status changes that
				// may not trigger the items live query in all edge cases.
				const countQuery = `SELECT COUNT(*) as count FROM notifications 
					WHERE user_id = $1 
					AND (search_space_id = $2 OR search_space_id IS NULL)
					AND created_at > '${cutoffDate}'
					AND read = false
					${typeFilter}`;

				const countLiveQuery = await db.live.query<{ count: number | string }>(countQuery, [
					uid,
					spaceId,
				]);

				if (!mounted) {
					countLiveQuery.unsubscribe?.();
					return;
				}

				countLiveQuery.subscribe((result: { rows: Array<{ count: number | string }> }) => {
					if (!mounted || !result.rows?.[0] || !initialLoadDoneRef.current) return;
					if (olderUnreadOffsetRef.current === null) return;
					const liveRecentUnread = Number(result.rows[0].count) || 0;
					setUnreadCount(olderUnreadOffsetRef.current + liveRecentUnread);
				});

				unreadLiveQueryRef.current = countLiveQuery;
			} catch (err) {
				console.error(`[useInbox:${category}] Electric setup failed:`, err);
			}
		}

		setupElectricRealtime();

		return () => {
			mounted = false;
			// Only clean up live queries — sync shape is shared across instances
			if (liveQueryRef.current) {
				try {
					liveQueryRef.current.unsubscribe?.();
				} catch {
					/* PGlite may be closed */
				}
				liveQueryRef.current = null;
			}
			if (unreadLiveQueryRef.current) {
				try {
					unreadLiveQueryRef.current.unsubscribe?.();
				} catch {
					/* PGlite may be closed */
				}
				unreadLiveQueryRef.current = null;
			}
		};
	}, [userId, searchSpaceId, electricClient, category]);

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
