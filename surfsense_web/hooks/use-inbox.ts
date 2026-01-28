"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { InboxItem, InboxItemTypeEnum } from "@/contracts/types/inbox.types";
import { notificationsApiService } from "@/lib/apis/notifications-api.service";
import type { SyncHandle } from "@/lib/electric/client";
import { useElectricClient } from "@/lib/electric/context";

export type { InboxItem, InboxItemTypeEnum } from "@/contracts/types/inbox.types";

const PAGE_SIZE = 50;
const SYNC_WINDOW_DAYS = 14;

/**
 * Check if an item is older than the sync window
 */
function isOlderThanSyncWindow(createdAt: string): boolean {
	const cutoffDate = new Date();
	cutoffDate.setDate(cutoffDate.getDate() - SYNC_WINDOW_DAYS);
	return new Date(createdAt) < cutoffDate;
}

/**
 * Deduplicate by ID and sort by created_at descending.
 * This is the SINGLE source of truth for deduplication - prevents race conditions.
 */
function deduplicateAndSort(items: InboxItem[]): InboxItem[] {
	const seen = new Map<number, InboxItem>();
	for (const item of items) {
		if (!seen.has(item.id)) {
			seen.set(item.id, item);
		}
	}
	return Array.from(seen.values()).sort(
		(a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
	);
}

/**
 * Calculate the cutoff date for sync window
 */
function getSyncCutoffDate(): string {
	const cutoff = new Date();
	cutoff.setDate(cutoff.getDate() - SYNC_WINDOW_DAYS);
	return cutoff.toISOString();
}

/**
 * Convert a date value to ISO string format
 */
function toISOString(date: string | Date | null | undefined): string | null {
	if (!date) return null;
	if (date instanceof Date) return date.toISOString();
	if (typeof date === "string") {
		if (date.includes("T")) return date;
		try {
			return new Date(date).toISOString();
		} catch {
			return date;
		}
	}
	return null;
}

/**
 * Hook for managing inbox items with Electric SQL real-time sync + API fallback
 *
 * Architecture (Simplified & Race-Condition Free):
 * - Electric SQL: Syncs recent items (within SYNC_WINDOW_DAYS) for real-time updates
 * - Live Query: Provides reactive first page from PGLite
 * - API: Handles all pagination (more reliable than mixing with Electric)
 *
 * Key Design Decisions:
 * 1. No mutable refs for cursor - cursor computed from current state
 * 2. Single deduplicateAndSort function - prevents inconsistencies
 * 3. Filter-based preservation in live query - prevents data loss
 * 4. Auto-fetch from API when Electric returns 0 items
 *
 * @param userId - The user ID to fetch inbox items for
 * @param searchSpaceId - The search space ID to filter inbox items
 * @param typeFilter - Optional inbox item type to filter by
 */
export function useInbox(
	userId: string | null,
	searchSpaceId: number | null,
	typeFilter: InboxItemTypeEnum | null = null
) {
	const electricClient = useElectricClient();

	const [inboxItems, setInboxItems] = useState<InboxItem[]>([]);
	const [loading, setLoading] = useState(true);
	const [loadingMore, setLoadingMore] = useState(false);
	const [hasMore, setHasMore] = useState(true);
	const [error, setError] = useState<Error | null>(null);

	// Split unread count tracking for accurate counts with 14-day sync window
	// olderUnreadCount = unread items OLDER than sync window (from server, static until reconciliation)
	// recentUnreadCount = unread items within sync window (from live query, real-time)
	const [olderUnreadCount, setOlderUnreadCount] = useState(0);
	const [recentUnreadCount, setRecentUnreadCount] = useState(0);

	const syncHandleRef = useRef<SyncHandle | null>(null);
	const liveQueryRef = useRef<{ unsubscribe: () => void } | null>(null);
	const userSyncKeyRef = useRef<string | null>(null);
	const unreadCountLiveQueryRef = useRef<{ unsubscribe: () => void } | null>(null);

	// Total unread = older (static from server) + recent (live from Electric)
	const totalUnreadCount = olderUnreadCount + recentUnreadCount;

	// EFFECT 1: Electric SQL sync for real-time updates
	useEffect(() => {
		if (!userId || !electricClient) {
			setLoading(!electricClient);
			return;
		}

		const client = electricClient;
		let mounted = true;

		async function startSync() {
			try {
				const cutoffDate = getSyncCutoffDate();
				const userSyncKey = `inbox_${userId}_${cutoffDate}`;

				// Skip if already syncing with this key
				if (userSyncKeyRef.current === userSyncKey) return;

				// Clean up previous sync
				if (syncHandleRef.current) {
					syncHandleRef.current.unsubscribe();
					syncHandleRef.current = null;
				}

				console.log("[useInbox] Starting sync for:", userId);
				userSyncKeyRef.current = userSyncKey;

				const handle = await client.syncShape({
					table: "notifications",
					where: `user_id = '${userId}' AND created_at > '${cutoffDate}'`,
					primaryKey: ["id"],
				});

				// Wait for initial sync with timeout
				if (!handle.isUpToDate && handle.initialSyncPromise) {
					await Promise.race([
						handle.initialSyncPromise,
						new Promise((resolve) => setTimeout(resolve, 3000)),
					]);
				}

				if (!mounted) {
					handle.unsubscribe();
					return;
				}

				syncHandleRef.current = handle;
				setLoading(false);
				setError(null);
			} catch (err) {
				if (!mounted) return;
				console.error("[useInbox] Sync failed:", err);
				setError(err instanceof Error ? err : new Error("Sync failed"));
				setLoading(false);
			}
		}

		startSync();

		return () => {
			mounted = false;
			userSyncKeyRef.current = null;
			if (syncHandleRef.current) {
				syncHandleRef.current.unsubscribe();
				syncHandleRef.current = null;
			}
		};
	}, [userId, electricClient]);

	// Reset when filters change
	useEffect(() => {
		setHasMore(true);
		setInboxItems([]);
		// Reset count states - will be refetched by the unread count effect
		setOlderUnreadCount(0);
		setRecentUnreadCount(0);
	}, [userId, searchSpaceId, typeFilter]);

	// EFFECT 2: Live query for real-time updates + auto-fetch from API if empty
	useEffect(() => {
		if (!userId || !electricClient) return;

		const client = electricClient;
		let mounted = true;

		async function setupLiveQuery() {
			// Clean up previous live query
			if (liveQueryRef.current) {
				liveQueryRef.current.unsubscribe();
				liveQueryRef.current = null;
			}

			try {
				const cutoff = getSyncCutoffDate();

				const query = `SELECT * FROM notifications 
					WHERE user_id = $1 
					AND (search_space_id = $2 OR search_space_id IS NULL)
					AND created_at > '${cutoff}'
					${typeFilter ? "AND type = $3" : ""}
					ORDER BY created_at DESC
					LIMIT ${PAGE_SIZE}`;

				const params = typeFilter ? [userId, searchSpaceId, typeFilter] : [userId, searchSpaceId];

				const db = client.db as any;

				// Initial fetch from PGLite - no validation needed, schema is enforced by Electric SQL sync
				const result = await client.db.query<InboxItem>(query, params);

				if (mounted && result.rows) {
					const items = deduplicateAndSort(result.rows);
					setInboxItems(items);

					// AUTO-FETCH: If Electric returned 0 items, check API for older items
					// This handles the edge case where user has no recent notifications
					// but has older ones outside the sync window
					if (items.length === 0) {
						console.log(
							"[useInbox] Electric returned 0 items, checking API for older notifications"
						);
						try {
							// Use the API service with proper Zod validation for API responses
							const data = await notificationsApiService.getNotifications({
								queryParams: {
									search_space_id: searchSpaceId ?? undefined,
									type: typeFilter ?? undefined,
									limit: PAGE_SIZE,
								},
							});

							if (mounted) {
								if (data.items.length > 0) {
									setInboxItems(data.items);
								}
								setHasMore(data.has_more);
							}
						} catch (err) {
							console.error("[useInbox] API fallback failed:", err);
						}
					}
				}

				// Set up live query for real-time updates
				if (db.live?.query) {
					const liveQuery = await db.live.query(query, params);

					if (!mounted) {
						liveQuery.unsubscribe?.();
						return;
					}

					if (liveQuery.subscribe) {
						// Live query data comes from PGlite - no validation needed
						liveQuery.subscribe((result: { rows: InboxItem[] }) => {
							if (mounted && result.rows) {
								const liveItems = result.rows;

								setInboxItems((prev) => {
									const liveItemIds = new Set(liveItems.map((item) => item.id));

									// FIXED: Keep ALL items not in live result (not just slice)
									// This prevents data loss when new notifications push items
									// out of the LIMIT window
									const itemsToKeep = prev.filter((item) => !liveItemIds.has(item.id));

									return deduplicateAndSort([...liveItems, ...itemsToKeep]);
								});
							}
						});
					}

					if (liveQuery.unsubscribe) {
						liveQueryRef.current = liveQuery;
					}
				}
			} catch (err) {
				console.error("[useInbox] Live query error:", err);
			}
		}

		setupLiveQuery();

		return () => {
			mounted = false;
			if (liveQueryRef.current) {
				liveQueryRef.current.unsubscribe();
				liveQueryRef.current = null;
			}
		};
	}, [userId, searchSpaceId, typeFilter, electricClient]);

	// EFFECT 3: Dedicated unread count sync with split tracking
	// - Fetches server count on mount (accurate total)
	// - Sets up live query for recent count (real-time updates)
	// - Handles items older than sync window separately
	useEffect(() => {
		if (!userId || !electricClient) return;

		const client = electricClient;
		let mounted = true;

		async function setupUnreadCountSync() {
			// Cleanup previous live query
			if (unreadCountLiveQueryRef.current) {
				unreadCountLiveQueryRef.current.unsubscribe();
				unreadCountLiveQueryRef.current = null;
			}

			try {
				// STEP 1: Fetch server counts (total and recent) - guaranteed accurate
				console.log(
					"[useInbox] Fetching unread count from server",
					typeFilter ? `for type: ${typeFilter}` : "for all types"
				);
				const serverCounts = await notificationsApiService.getUnreadCount(
					searchSpaceId ?? undefined,
					typeFilter ?? undefined
				);

				if (mounted) {
					// Calculate older count = total - recent
					const olderCount = serverCounts.total_unread - serverCounts.recent_unread;
					setOlderUnreadCount(olderCount);
					setRecentUnreadCount(serverCounts.recent_unread);
					console.log(
						`[useInbox] Server counts: total=${serverCounts.total_unread}, recent=${serverCounts.recent_unread}, older=${olderCount}`
					);
				}

				// STEP 2: Set up PGLite live query for RECENT unread count only
				// This provides real-time updates for notifications within sync window
				const db = client.db as any;
				const cutoff = getSyncCutoffDate();

				// Count query - NO LIMIT, counts all unread in synced window
				const countQuery = `
					SELECT COUNT(*) as count FROM notifications 
					WHERE user_id = $1 
					AND (search_space_id = $2 OR search_space_id IS NULL)
					AND created_at > '${cutoff}'
					AND read = false
					${typeFilter ? "AND type = $3" : ""}
				`;
				const params = typeFilter ? [userId, searchSpaceId, typeFilter] : [userId, searchSpaceId];

				if (db.live?.query) {
					const liveQuery = await db.live.query(countQuery, params);

					if (!mounted) {
						liveQuery.unsubscribe?.();
						return;
					}

					if (liveQuery.subscribe) {
						liveQuery.subscribe((result: { rows: Array<{ count: number | string }> }) => {
							if (mounted && result.rows?.[0]) {
								const liveCount = Number(result.rows[0].count) || 0;
								// Update recent count from live query
								// This fires in real-time when Electric syncs new/updated notifications
								setRecentUnreadCount(liveCount);
							}
						});
					}

					if (liveQuery.unsubscribe) {
						unreadCountLiveQueryRef.current = liveQuery;
					}
				}
			} catch (err) {
				console.error("[useInbox] Unread count sync error:", err);
				// On error, counts will remain at 0 or previous values
				// The items-based count will be the fallback
			}
		}

		setupUnreadCountSync();

		return () => {
			mounted = false;
			if (unreadCountLiveQueryRef.current) {
				unreadCountLiveQueryRef.current.unsubscribe();
				unreadCountLiveQueryRef.current = null;
			}
		};
	}, [userId, searchSpaceId, typeFilter, electricClient]);

	// loadMore - Pure cursor-based pagination, no race conditions
	// Cursor is computed from current state, not stored in refs
	const loadMore = useCallback(async () => {
		// Removed inboxItems.length === 0 check to allow loading older items
		// when Electric returns 0 items
		if (!userId || loadingMore || !hasMore) return;

		setLoadingMore(true);

		try {
			// Cursor is computed from current state - no stale refs possible
			const oldestItem = inboxItems.length > 0 ? inboxItems[inboxItems.length - 1] : null;
			const beforeDate = oldestItem ? toISOString(oldestItem.created_at) : null;

			console.log("[useInbox] Loading more, before:", beforeDate ?? "none (initial)");

			// Use the API service with proper Zod validation
			const data = await notificationsApiService.getNotifications({
				queryParams: {
					search_space_id: searchSpaceId ?? undefined,
					type: typeFilter ?? undefined,
					before_date: beforeDate ?? undefined,
					limit: PAGE_SIZE,
				},
			});

			if (data.items.length > 0) {
				// Functional update ensures we always merge with latest state
				// Items are already validated by the API service
				setInboxItems((prev) => deduplicateAndSort([...prev, ...data.items]));
			}

			// Use API's has_more flag
			setHasMore(data.has_more);
		} catch (err) {
			console.error("[useInbox] Load more failed:", err);
		} finally {
			setLoadingMore(false);
		}
	}, [userId, searchSpaceId, typeFilter, loadingMore, hasMore, inboxItems]);

	// Mark inbox item as read with optimistic update
	// Handles both recent items (live query updates count) and older items (manual count decrement)
	const markAsRead = useCallback(
		async (itemId: number) => {
			// Find the item to check if it's older than sync window
			const item = inboxItems.find((i) => i.id === itemId);
			const isOlderItem = item && !item.read && isOlderThanSyncWindow(item.created_at);

			// Optimistic update: mark as read immediately for instant UI feedback
			setInboxItems((prev) => prev.map((i) => (i.id === itemId ? { ...i, read: true } : i)));

			// If older item, manually decrement older count
			// (live query won't see items outside sync window)
			if (isOlderItem) {
				setOlderUnreadCount((prev) => Math.max(0, prev - 1));
			}

			try {
				// Use the API service with proper Zod validation
				const result = await notificationsApiService.markAsRead({ notificationId: itemId });

				if (!result.success) {
					// Rollback on error
					setInboxItems((prev) => prev.map((i) => (i.id === itemId ? { ...i, read: false } : i)));
					if (isOlderItem) {
						setOlderUnreadCount((prev) => prev + 1);
					}
				}
				// If successful, Electric SQL will sync the change and live query will update
				// This ensures eventual consistency even if optimistic update was wrong
				return result.success;
			} catch (err) {
				console.error("Failed to mark as read:", err);
				// Rollback on error
				setInboxItems((prev) => prev.map((i) => (i.id === itemId ? { ...i, read: false } : i)));
				if (isOlderItem) {
					setOlderUnreadCount((prev) => prev + 1);
				}
				return false;
			}
		},
		[inboxItems]
	);

	// Mark all inbox items as read with optimistic update
	// Resets both older and recent counts to 0
	const markAllAsRead = useCallback(async () => {
		// Store previous counts for potential rollback
		const prevOlderCount = olderUnreadCount;
		const prevRecentCount = recentUnreadCount;

		// Optimistic update: mark all as read immediately for instant UI feedback
		setInboxItems((prev) => prev.map((item) => ({ ...item, read: true })));
		setOlderUnreadCount(0);
		setRecentUnreadCount(0);

		try {
			// Use the API service with proper Zod validation
			const result = await notificationsApiService.markAllAsRead();

			if (!result.success) {
				console.error("Failed to mark all as read");
				// Rollback counts on error
				setOlderUnreadCount(prevOlderCount);
				setRecentUnreadCount(prevRecentCount);
			}
			// Electric SQL will sync and live query will ensure consistency
			return result.success;
		} catch (err) {
			console.error("Failed to mark all as read:", err);
			// Rollback counts on error
			setOlderUnreadCount(prevOlderCount);
			setRecentUnreadCount(prevRecentCount);
			return false;
		}
	}, [olderUnreadCount, recentUnreadCount]);

	return {
		inboxItems,
		unreadCount: totalUnreadCount,
		markAsRead,
		markAllAsRead,
		loading,
		loadingMore,
		hasMore,
		loadMore,
		isUsingApiFallback: true, // Always use API for pagination
		error,
	};
}
