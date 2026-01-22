"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { InboxItem, InboxItemTypeEnum } from "@/contracts/types/inbox.types";
import { authenticatedFetch } from "@/lib/auth-utils";
import type { SyncHandle } from "@/lib/electric/client";
import { useElectricClient } from "@/lib/electric/context";

export type { InboxItem, InboxItemTypeEnum } from "@/contracts/types/inbox.types";

const PAGE_SIZE = 50;
const SYNC_WINDOW_DAYS = 14;

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
	const [totalUnreadCount, setTotalUnreadCount] = useState(0);
	const [loading, setLoading] = useState(true);
	const [loadingMore, setLoadingMore] = useState(false);
	const [hasMore, setHasMore] = useState(true);
	const [error, setError] = useState<Error | null>(null);

	const syncHandleRef = useRef<SyncHandle | null>(null);
	const liveQueryRef = useRef<{ unsubscribe: () => void } | null>(null);
	const unreadCountLiveQueryRef = useRef<{ unsubscribe: () => void } | null>(null);
	const userSyncKeyRef = useRef<string | null>(null);

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

				const params = typeFilter
					? [userId, searchSpaceId, typeFilter]
					: [userId, searchSpaceId];

				const db = client.db as any;

				// Initial fetch from PGLite
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
							const apiParams = new URLSearchParams();
							if (searchSpaceId !== null) {
								apiParams.append("search_space_id", String(searchSpaceId));
							}
							if (typeFilter) {
								apiParams.append("type", typeFilter);
							}
							apiParams.append("limit", String(PAGE_SIZE));

							const response = await authenticatedFetch(
								`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/notifications?${apiParams.toString()}`
							);

							if (response.ok && mounted) {
								const data = await response.json();
								const apiItems: InboxItem[] = data.items.map((item: any) => ({
									...item,
									metadata: item.metadata || {},
								}));

								if (apiItems.length > 0) {
									setInboxItems(apiItems);
								}
								setHasMore(data.has_more ?? apiItems.length === PAGE_SIZE);
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
						liveQuery.subscribe((result: { rows: InboxItem[] }) => {
							if (mounted && result.rows) {
								setInboxItems((prev) => {
									const liveItems = result.rows;
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

	// EFFECT 3: Unread count with live updates
	useEffect(() => {
		if (!userId || !electricClient) return;

		const client = electricClient;
		let mounted = true;

		async function updateUnreadCount() {
			if (unreadCountLiveQueryRef.current) {
				unreadCountLiveQueryRef.current.unsubscribe();
				unreadCountLiveQueryRef.current = null;
			}

			try {
				const cutoff = getSyncCutoffDate();
				const query = `SELECT COUNT(*) as count FROM notifications 
					WHERE user_id = $1 
					AND (search_space_id = $2 OR search_space_id IS NULL)
					AND read = false
					AND created_at > '${cutoff}'`;

				const result = await client.db.query<{ count: number }>(query, [
					userId,
					searchSpaceId,
				]);
				if (mounted && result.rows?.[0]) {
					setTotalUnreadCount(Number(result.rows[0].count) || 0);
				}

				const db = client.db as any;
				if (db.live?.query) {
					const liveQuery = await db.live.query(query, [userId, searchSpaceId]);

					if (!mounted) {
						liveQuery.unsubscribe?.();
						return;
					}

					if (liveQuery.subscribe) {
						liveQuery.subscribe((result: { rows: { count: number }[] }) => {
							if (mounted && result.rows?.[0]) {
								setTotalUnreadCount(Number(result.rows[0].count) || 0);
							}
						});
					}

					if (liveQuery.unsubscribe) {
						unreadCountLiveQueryRef.current = liveQuery;
					}
				}
			} catch (err) {
				console.error("[useInbox] Unread count error:", err);
			}
		}

		updateUnreadCount();

		return () => {
			mounted = false;
			if (unreadCountLiveQueryRef.current) {
				unreadCountLiveQueryRef.current.unsubscribe();
				unreadCountLiveQueryRef.current = null;
			}
		};
	}, [userId, searchSpaceId, electricClient]);

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

			const params = new URLSearchParams();
			if (searchSpaceId !== null) {
				params.append("search_space_id", String(searchSpaceId));
			}
			if (typeFilter) {
				params.append("type", typeFilter);
			}
			// Only add before_date if we have a cursor
			// Without before_date, API returns newest items first
			if (beforeDate) {
				params.append("before_date", beforeDate);
			}
			params.append("limit", String(PAGE_SIZE));

			console.log("[useInbox] Loading more, before:", beforeDate ?? "none (initial)");

			const response = await authenticatedFetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/notifications?${params.toString()}`
			);

			if (!response.ok) {
				throw new Error("Failed to fetch notifications");
			}

			const data = await response.json();
			const apiItems: InboxItem[] = data.items.map((item: any) => ({
				...item,
				metadata: item.metadata || {},
			}));

			if (apiItems.length > 0) {
				// Functional update ensures we always merge with latest state
				setInboxItems((prev) => deduplicateAndSort([...prev, ...apiItems]));
			}

			// Use API's has_more flag if available, otherwise check count
			setHasMore(data.has_more ?? apiItems.length === PAGE_SIZE);
		} catch (err) {
			console.error("[useInbox] Load more failed:", err);
		} finally {
			setLoadingMore(false);
		}
	}, [userId, searchSpaceId, typeFilter, loadingMore, hasMore, inboxItems]);

	// Mark inbox item as read
	const markAsRead = useCallback(async (itemId: number) => {
		try {
			const response = await authenticatedFetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/notifications/${itemId}/read`,
				{ method: "PATCH" }
			);
			return response.ok;
		} catch (err) {
			console.error("Failed to mark as read:", err);
			return false;
		}
	}, []);

	// Mark all inbox items as read
	const markAllAsRead = useCallback(async () => {
		try {
			const response = await authenticatedFetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/notifications/read-all`,
				{ method: "PATCH" }
			);
			return response.ok;
		} catch (err) {
			console.error("Failed to mark all as read:", err);
			return false;
		}
	}, []);

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
