"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { InboxItem, InboxItemTypeEnum } from "@/contracts/types/inbox.types";
import { authenticatedFetch } from "@/lib/auth-utils";
import type { SyncHandle } from "@/lib/electric/client";
import { useElectricClient } from "@/lib/electric/context";

export type { InboxItem, InboxItemTypeEnum } from "@/contracts/types/inbox.types";

/**
 * Hook for managing inbox items with Electric SQL real-time sync
 *
 * Uses the Electric client from context (provided by ElectricProvider)
 * instead of initializing its own - prevents race conditions and memory leaks
 *
 * Architecture:
 * - User-level sync: Syncs ALL inbox items for a user (runs once per user)
 * - Search-space-level query: Filters inbox items by searchSpaceId (updates on search space change)
 *
 * This separation ensures smooth transitions when switching search spaces (no flash).
 *
 * @param userId - The user ID to fetch inbox items for
 * @param searchSpaceId - The search space ID to filter inbox items (null shows global items only)
 * @param typeFilter - Optional inbox item type to filter by (null shows all types)
 */
export function useInbox(
	userId: string | null,
	searchSpaceId: number | null,
	typeFilter: InboxItemTypeEnum | null = null
) {
	// Get Electric client from context - ElectricProvider handles initialization
	const electricClient = useElectricClient();

	const [inboxItems, setInboxItems] = useState<InboxItem[]>([]);
	const [totalUnreadCount, setTotalUnreadCount] = useState(0);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<Error | null>(null);
	const syncHandleRef = useRef<SyncHandle | null>(null);
	const liveQueryRef = useRef<{ unsubscribe: () => void } | null>(null);
	const unreadCountLiveQueryRef = useRef<{ unsubscribe: () => void } | null>(null);

	// Track user-level sync key to prevent duplicate sync subscriptions
	const userSyncKeyRef = useRef<string | null>(null);

	// EFFECT 1: User-level sync - runs once per user, syncs ALL inbox items
	useEffect(() => {
		if (!userId || !electricClient) {
			setLoading(!electricClient);
			return;
		}

		const userSyncKey = `inbox_${userId}`;
		if (userSyncKeyRef.current === userSyncKey) {
			// Already syncing for this user
			return;
		}

		// Capture electricClient to satisfy TypeScript in async function
		const client = electricClient;
		let mounted = true;
		userSyncKeyRef.current = userSyncKey;

		async function startUserSync() {
			try {
				console.log("[useInbox] Starting user-level sync for:", userId);

				// Sync ALL inbox items for this user (cached via syncShape caching)
				// Note: Backend table is still named "notifications"
				const handle = await client.syncShape({
					table: "notifications",
					where: `user_id = '${userId}'`,
					primaryKey: ["id"],
				});

				console.log("[useInbox] User sync started:", {
					isUpToDate: handle.isUpToDate,
				});

				// Wait for initial sync with timeout
				if (!handle.isUpToDate && handle.initialSyncPromise) {
					try {
						await Promise.race([
							handle.initialSyncPromise,
							new Promise((resolve) => setTimeout(resolve, 2000)),
						]);
					} catch (syncErr) {
						console.error("[useInbox] Initial sync failed:", syncErr);
					}
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
				console.error("[useInbox] Failed to start user sync:", err);
				setError(err instanceof Error ? err : new Error("Failed to sync inbox"));
				setLoading(false);
			}
		}

		startUserSync();

		return () => {
			mounted = false;
			userSyncKeyRef.current = null;

			if (syncHandleRef.current) {
				syncHandleRef.current.unsubscribe();
				syncHandleRef.current = null;
			}
		};
	}, [userId, electricClient]);

	// EFFECT 2: Search-space-level query - updates when searchSpaceId or typeFilter changes
	// This runs independently of sync, allowing smooth transitions between search spaces
	useEffect(() => {
		if (!userId || !electricClient) {
			return;
		}

		// Capture electricClient to satisfy TypeScript in async function
		const client = electricClient;
		let mounted = true;

		async function updateQuery() {
			// Clean up previous live query (but DON'T clear inbox items - keep showing old until new arrive)
			if (liveQueryRef.current) {
				liveQueryRef.current.unsubscribe();
				liveQueryRef.current = null;
			}

			try {
				console.log(
					"[useInbox] Updating query for searchSpace:",
					searchSpaceId,
					"typeFilter:",
					typeFilter
				);

				// Build query with optional type filter
				// Note: Backend table is still named "notifications"
				const baseQuery = `SELECT * FROM notifications 
					 WHERE user_id = $1 
					 AND (search_space_id = $2 OR search_space_id IS NULL)`;
				const typeClause = typeFilter ? ` AND type = $3` : "";
				const orderClause = ` ORDER BY created_at DESC`;
				const fullQuery = baseQuery + typeClause + orderClause;
				const params = typeFilter ? [userId, searchSpaceId, typeFilter] : [userId, searchSpaceId];

				// Fetch inbox items for current search space immediately
				const result = await client.db.query<InboxItem>(fullQuery, params);

				if (mounted) {
					setInboxItems(result.rows || []);
				}

				// Set up live query for real-time updates
				const db = client.db as any;

				if (db.live?.query && typeof db.live.query === "function") {
					const liveQuery = await db.live.query(fullQuery, params);

					if (!mounted) {
						liveQuery.unsubscribe?.();
						return;
					}

					// Set initial results from live query
					if (liveQuery.initialResults?.rows) {
						setInboxItems(liveQuery.initialResults.rows);
					} else if (liveQuery.rows) {
						setInboxItems(liveQuery.rows);
					}

					// Subscribe to changes
					if (typeof liveQuery.subscribe === "function") {
						liveQuery.subscribe((result: { rows: InboxItem[] }) => {
							if (mounted && result.rows) {
								setInboxItems(result.rows);
							}
						});
					}

					if (typeof liveQuery.unsubscribe === "function") {
						liveQueryRef.current = liveQuery;
					}
				}
			} catch (err) {
				console.error("[useInbox] Failed to update query:", err);
			}
		}

		updateQuery();

		return () => {
			mounted = false;
			if (liveQueryRef.current) {
				liveQueryRef.current.unsubscribe();
				liveQueryRef.current = null;
			}
		};
	}, [userId, searchSpaceId, typeFilter, electricClient]);

	// EFFECT 3: Total unread count - independent of type filter
	// This ensures the badge count stays consistent regardless of active filter
	useEffect(() => {
		if (!userId || !electricClient) {
			return;
		}

		// Capture electricClient to satisfy TypeScript in async function
		const client = electricClient;
		let mounted = true;

		async function updateUnreadCount() {
			// Clean up previous live query
			if (unreadCountLiveQueryRef.current) {
				unreadCountLiveQueryRef.current.unsubscribe();
				unreadCountLiveQueryRef.current = null;
			}

			try {
				// Note: Backend table is still named "notifications"
				const countQuery = `SELECT COUNT(*) as count FROM notifications 
					 WHERE user_id = $1 
					 AND (search_space_id = $2 OR search_space_id IS NULL)
					 AND read = false`;

				// Fetch initial count
				const result = await client.db.query<{ count: number }>(countQuery, [
					userId,
					searchSpaceId,
				]);

				if (mounted && result.rows?.[0]) {
					setTotalUnreadCount(Number(result.rows[0].count) || 0);
				}

				// Set up live query for real-time updates
				const db = client.db as any;

				if (db.live?.query && typeof db.live.query === "function") {
					const liveQuery = await db.live.query(countQuery, [userId, searchSpaceId]);

					if (!mounted) {
						liveQuery.unsubscribe?.();
						return;
					}

					// Set initial results from live query
					if (liveQuery.initialResults?.rows?.[0]) {
						setTotalUnreadCount(Number(liveQuery.initialResults.rows[0].count) || 0);
					} else if (liveQuery.rows?.[0]) {
						setTotalUnreadCount(Number(liveQuery.rows[0].count) || 0);
					}

					// Subscribe to changes
					if (typeof liveQuery.subscribe === "function") {
						liveQuery.subscribe((result: { rows: { count: number }[] }) => {
							if (mounted && result.rows?.[0]) {
								setTotalUnreadCount(Number(result.rows[0].count) || 0);
							}
						});
					}

					if (typeof liveQuery.unsubscribe === "function") {
						unreadCountLiveQueryRef.current = liveQuery;
					}
				}
			} catch (err) {
				console.error("[useInbox] Failed to update unread count:", err);
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

	// Mark inbox item as read via backend API
	const markAsRead = useCallback(async (itemId: number) => {
		try {
			// Note: Backend API endpoint is still /notifications/
			const response = await authenticatedFetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/notifications/${itemId}/read`,
				{ method: "PATCH" }
			);

			if (!response.ok) {
				const error = await response.json().catch(() => ({ detail: "Failed to mark as read" }));
				throw new Error(error.detail || "Failed to mark inbox item as read");
			}

			return true;
		} catch (err) {
			console.error("Failed to mark inbox item as read:", err);
			return false;
		}
	}, []);

	// Mark all inbox items as read via backend API
	const markAllAsRead = useCallback(async () => {
		try {
			// Note: Backend API endpoint is still /notifications/
			const response = await authenticatedFetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/notifications/read-all`,
				{ method: "PATCH" }
			);

			if (!response.ok) {
				const error = await response.json().catch(() => ({ detail: "Failed to mark all as read" }));
				throw new Error(error.detail || "Failed to mark all inbox items as read");
			}

			return true;
		} catch (err) {
			console.error("Failed to mark all inbox items as read:", err);
			return false;
		}
	}, []);

	// Archive/unarchive an inbox item via backend API
	const archiveItem = useCallback(async (itemId: number, archived: boolean) => {
		try {
			const response = await authenticatedFetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/notifications/${itemId}/archive`,
				{
					method: "PATCH",
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify({ archived }),
				}
			);

			if (!response.ok) {
				const error = await response.json().catch(() => ({ detail: "Failed to update archive status" }));
				throw new Error(error.detail || "Failed to update inbox item archive status");
			}

			return true;
		} catch (err) {
			console.error("Failed to update inbox item archive status:", err);
			return false;
		}
	}, []);

	return {
		inboxItems,
		unreadCount: totalUnreadCount,
		markAsRead,
		markAllAsRead,
		archiveItem,
		loading,
		error,
	};
}

