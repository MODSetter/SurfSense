"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { InboxItem } from "@/contracts/types/inbox.types";
import { notificationsApiService } from "@/lib/apis/notifications-api.service";
import type { SyncHandle } from "@/lib/electric/client";
import { useElectricClient } from "@/lib/electric/context";

export type { InboxItem, InboxItemTypeEnum } from "@/contracts/types/inbox.types";

const INITIAL_PAGE_SIZE = 50;
const SCROLL_PAGE_SIZE = 30;
const SYNC_WINDOW_DAYS = 4;

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
 * Architecture (Documents pattern):
 * 1. API is the PRIMARY data source — fetches first page on mount
 * 2. Electric provides REAL-TIME updates (new items, status changes, read state)
 * 3. Baseline pattern prevents duplicates between API and Electric
 * 4. Single instance serves both Comments and Status tabs
 *
 * Unread count strategy:
 * - API provides the total on mount (ground truth across all time)
 * - Electric live query counts unread within SYNC_WINDOW_DAYS
 * - olderUnreadOffsetRef bridges the gap: total = offset + recent
 * - Optimistic updates adjust both the count and the offset (for old items)
 *
 * @param userId - The user ID to fetch inbox items for
 * @param searchSpaceId - The search space ID to filter inbox items
 */
export function useInbox(
	userId: string | null,
	searchSpaceId: number | null,
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
	const syncHandleRef = useRef<SyncHandle | null>(null);
	const liveQueryRef = useRef<{ unsubscribe?: () => void } | null>(null);
	const unreadLiveQueryRef = useRef<{ unsubscribe?: () => void } | null>(null);

	// Unread count offset: number of unread items OLDER than the sync window.
	// Computed once from (API total - first Electric recent count), then adjusted
	// when the user marks old items as read.
	const olderUnreadOffsetRef = useRef<number | null>(null);
	const apiUnreadTotalRef = useRef(0);

	// EFFECT 1: Fetch first page + unread count from API when params change
	useEffect(() => {
		if (!userId || !searchSpaceId) return;

		let cancelled = false;

		setLoading(true);
		setInboxItems([]);
		setHasMore(false);
		initialLoadDoneRef.current = false;
		electricBaselineIdsRef.current = null;
		olderUnreadOffsetRef.current = null;
		apiUnreadTotalRef.current = 0;

		const fetchInitialData = async () => {
			try {
				const [notificationsResponse, unreadResponse] = await Promise.all([
					notificationsApiService.getNotifications({
						queryParams: {
							search_space_id: searchSpaceId,
							limit: INITIAL_PAGE_SIZE,
						},
					}),
					notificationsApiService.getUnreadCount(searchSpaceId),
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
				console.error("[useInbox] Initial load failed:", err);
				setError(err instanceof Error ? err : new Error("Failed to load notifications"));
			} finally {
				if (!cancelled) setLoading(false);
			}
		};

		fetchInitialData();
		return () => { cancelled = true; };
	}, [userId, searchSpaceId]);

	// EFFECT 2: Electric sync + live query for real-time updates
	useEffect(() => {
		if (!userId || !searchSpaceId || !electricClient) return;

		const uid = userId;
		const spaceId = searchSpaceId;
		const client = electricClient;
		let mounted = true;

		async function setupElectricRealtime() {
			if (syncHandleRef.current) {
				try { syncHandleRef.current.unsubscribe(); } catch { /* PGlite may be closed */ }
				syncHandleRef.current = null;
			}
			if (liveQueryRef.current) {
				try { liveQueryRef.current.unsubscribe?.(); } catch { /* PGlite may be closed */ }
				liveQueryRef.current = null;
			}
			if (unreadLiveQueryRef.current) {
				try { unreadLiveQueryRef.current.unsubscribe?.(); } catch { /* PGlite may be closed */ }
				unreadLiveQueryRef.current = null;
			}

			try {
				const cutoffDate = getSyncCutoffDate();

				const handle = await client.syncShape({
					table: "notifications",
					where: `user_id = '${uid}' AND created_at > '${cutoffDate}'`,
					primaryKey: ["id"],
				});

				if (!mounted) {
					handle.unsubscribe();
					return;
				}

				syncHandleRef.current = handle;

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

				const itemsQuery = `SELECT * FROM notifications 
					WHERE user_id = $1 
					AND (search_space_id = $2 OR search_space_id IS NULL)
					AND created_at > '${cutoffDate}'
					ORDER BY created_at DESC`;

				const liveQuery = await db.live.query<InboxItem>(itemsQuery, [uid, spaceId]);

				if (!mounted) {
					liveQuery.unsubscribe?.();
					return;
				}

				liveQuery.subscribe((result: { rows: InboxItem[] }) => {
					if (!mounted || !result.rows || !initialLoadDoneRef.current) return;

					const validItems = result.rows.filter((item) => item.id != null && item.title != null);
					const isFullySynced = syncHandleRef.current?.isUpToDate ?? false;
					const cutoff = new Date(getSyncCutoffDate());

					// Build a Map for O(1) lookups instead of .find() inside .map()
					const liveItemMap = new Map(validItems.map((d) => [d.id, d]));
					const liveIds = new Set(liveItemMap.keys());

					setInboxItems((prev) => {
						const prevIds = new Set(prev.map((d) => d.id));

						if (electricBaselineIdsRef.current === null) {
							electricBaselineIdsRef.current = new Set(liveIds);
						}

						const baseline = electricBaselineIdsRef.current;
						const newItems = validItems
							.filter((item) => {
								if (prevIds.has(item.id)) return false;
								if (baseline.has(item.id)) return false;
								return true;
							});

						for (const item of newItems) {
							baseline.add(item.id);
						}

						let updated = prev.map((item) => {
							const liveItem = liveItemMap.get(item.id);
							if (liveItem) return liveItem;
							return item;
						});

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
				});

				liveQueryRef.current = liveQuery;

				// Unread count live query — only covers the sync window.
				// Combined with olderUnreadOffsetRef to produce the full count.
				const countQuery = `SELECT COUNT(*) as count FROM notifications 
					WHERE user_id = $1 
					AND (search_space_id = $2 OR search_space_id IS NULL)
					AND created_at > '${cutoffDate}'
					AND read = false`;

				const countLiveQuery = await db.live.query<{ count: number | string }>(countQuery, [uid, spaceId]);

				if (!mounted) {
					countLiveQuery.unsubscribe?.();
					return;
				}

				countLiveQuery.subscribe((result: { rows: Array<{ count: number | string }> }) => {
					if (!mounted || !result.rows?.[0] || !initialLoadDoneRef.current) return;
					const liveRecentUnread = Number(result.rows[0].count) || 0;

					// First callback: compute how many unread are outside the sync window
					if (olderUnreadOffsetRef.current === null) {
						olderUnreadOffsetRef.current = Math.max(
							0,
							apiUnreadTotalRef.current - liveRecentUnread
						);
					}

					setUnreadCount(olderUnreadOffsetRef.current + liveRecentUnread);
				});

				unreadLiveQueryRef.current = countLiveQuery;
			} catch (err) {
				console.error("[useInbox] Electric setup failed:", err);
			}
		}

		setupElectricRealtime();

		return () => {
			mounted = false;
			if (syncHandleRef.current) {
				try { syncHandleRef.current.unsubscribe(); } catch { /* PGlite may be closed */ }
				syncHandleRef.current = null;
			}
			if (liveQueryRef.current) {
				try { liveQueryRef.current.unsubscribe?.(); } catch { /* PGlite may be closed */ }
				liveQueryRef.current = null;
			}
			if (unreadLiveQueryRef.current) {
				try { unreadLiveQueryRef.current.unsubscribe?.(); } catch { /* PGlite may be closed */ }
				unreadLiveQueryRef.current = null;
			}
		};
	}, [userId, searchSpaceId, electricClient]);

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
			console.error("[useInbox] Load more failed:", err);
		} finally {
			setLoadingMore(false);
		}
	}, [loadingMore, hasMore, userId, searchSpaceId, inboxItems]);

	// Mark single item as read with optimistic update
	const markAsRead = useCallback(
		async (itemId: number) => {
			const item = inboxItems.find((i) => i.id === itemId);
			if (!item || item.read) return true;

			const cutoff = new Date(getSyncCutoffDate());
			const isOlderItem = new Date(item.created_at) < cutoff;

			setInboxItems((prev) => prev.map((i) => (i.id === itemId ? { ...i, read: true } : i)));
			setUnreadCount((prev) => Math.max(0, prev - 1));

			// Adjust older offset so the next live query callback stays consistent
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
		const prevCount = unreadCount;
		const prevOffset = olderUnreadOffsetRef.current;

		setInboxItems((prev) => prev.map((item) => ({ ...item, read: true })));
		setUnreadCount(0);
		olderUnreadOffsetRef.current = 0;

		try {
			const result = await notificationsApiService.markAllAsRead();
			if (!result.success) {
				setUnreadCount(prevCount);
				olderUnreadOffsetRef.current = prevOffset;
			}
			return result.success;
		} catch (err) {
			console.error("Failed to mark all as read:", err);
			setUnreadCount(prevCount);
			olderUnreadOffsetRef.current = prevOffset;
			return false;
		}
	}, [unreadCount]);

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
