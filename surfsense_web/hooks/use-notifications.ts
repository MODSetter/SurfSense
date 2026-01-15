"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useElectricClient } from "@/lib/electric/context";
import type { SyncHandle } from "@/lib/electric/client";
import type { Notification } from "@/contracts/types/notification.types";
import { authenticatedFetch } from "@/lib/auth-utils";

export type { Notification } from "@/contracts/types/notification.types";

/**
 * Hook for managing notifications with Electric SQL real-time sync
 * 
 * Uses the Electric client from context (provided by ElectricProvider)
 * instead of initializing its own - prevents race conditions and memory leaks
 * 
 * Architecture:
 * - User-level sync: Syncs ALL notifications for a user (runs once per user)
 * - Search-space-level query: Filters notifications by searchSpaceId (updates on search space change)
 * 
 * This separation ensures smooth transitions when switching search spaces (no flash).
 * 
 * @param userId - The user ID to fetch notifications for
 * @param searchSpaceId - The search space ID to filter notifications (null shows global notifications only)
 */
export function useNotifications(userId: string | null, searchSpaceId: number | null) {
	// Get Electric client from context - ElectricProvider handles initialization
	const electricClient = useElectricClient();
	
	const [notifications, setNotifications] = useState<Notification[]>([]);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<Error | null>(null);
	const syncHandleRef = useRef<SyncHandle | null>(null);
	const liveQueryRef = useRef<{ unsubscribe: () => void } | null>(null);
	
	// Track user-level sync key to prevent duplicate sync subscriptions
	const userSyncKeyRef = useRef<string | null>(null);

	// EFFECT 1: User-level sync - runs once per user, syncs ALL notifications
	useEffect(() => {
		if (!userId || !electricClient) {
			setLoading(!electricClient);
			return;
		}

		const userSyncKey = `notifications_${userId}`;
		if (userSyncKeyRef.current === userSyncKey) {
			// Already syncing for this user
			return;
		}

		let mounted = true;
		userSyncKeyRef.current = userSyncKey;

		async function startUserSync() {
			try {
				console.log("[useNotifications] Starting user-level sync for:", userId);

				// Sync ALL notifications for this user (cached via syncShape caching)
				const handle = await electricClient.syncShape({
					table: "notifications",
					where: `user_id = '${userId}'`,
					primaryKey: ["id"],
				});

				console.log("[useNotifications] User sync started:", {
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
						console.error("[useNotifications] Initial sync failed:", syncErr);
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
				console.error("[useNotifications] Failed to start user sync:", err);
				setError(err instanceof Error ? err : new Error("Failed to sync notifications"));
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

	// EFFECT 2: Search-space-level query - updates when searchSpaceId changes
	// This runs independently of sync, allowing smooth transitions between search spaces
	useEffect(() => {
		if (!userId || !electricClient) {
			return;
		}

		let mounted = true;

		async function updateQuery() {
			// Clean up previous live query (but DON'T clear notifications - keep showing old until new arrive)
			if (liveQueryRef.current) {
				liveQueryRef.current.unsubscribe();
				liveQueryRef.current = null;
			}

			try {
				console.log("[useNotifications] Updating query for searchSpace:", searchSpaceId);

				// Fetch notifications for current search space immediately
				const result = await electricClient.db.query<Notification>(
					`SELECT * FROM notifications 
					 WHERE user_id = $1 
					 AND (search_space_id = $2 OR search_space_id IS NULL)
					 ORDER BY created_at DESC`,
					[userId, searchSpaceId]
				);
				
				if (mounted) {
					setNotifications(result.rows || []);
				}

				// Set up live query for real-time updates
				// eslint-disable-next-line @typescript-eslint/no-explicit-any
				const db = electricClient.db as any;

				if (db.live?.query && typeof db.live.query === "function") {
					const liveQuery = await db.live.query(
						`SELECT * FROM notifications 
						 WHERE user_id = $1 
						 AND (search_space_id = $2 OR search_space_id IS NULL)
						 ORDER BY created_at DESC`,
						[userId, searchSpaceId]
					);

					if (!mounted) {
						liveQuery.unsubscribe?.();
						return;
					}

					// Set initial results from live query
					if (liveQuery.initialResults?.rows) {
						setNotifications(liveQuery.initialResults.rows);
					} else if (liveQuery.rows) {
						setNotifications(liveQuery.rows);
					}

					// Subscribe to changes
					if (typeof liveQuery.subscribe === "function") {
						liveQuery.subscribe((result: { rows: Notification[] }) => {
							if (mounted && result.rows) {
								setNotifications(result.rows);
							}
						});
					}

					if (typeof liveQuery.unsubscribe === "function") {
						liveQueryRef.current = liveQuery;
					}
				}
			} catch (err) {
				console.error("[useNotifications] Failed to update query:", err);
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
	}, [userId, searchSpaceId, electricClient]);

	// Mark notification as read via backend API
	const markAsRead = useCallback(async (notificationId: number) => {
		try {
			const response = await authenticatedFetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/notifications/${notificationId}/read`,
				{ method: "PATCH" }
			);

			if (!response.ok) {
				const error = await response.json().catch(() => ({ detail: "Failed to mark as read" }));
				throw new Error(error.detail || "Failed to mark notification as read");
			}

			return true;
		} catch (err) {
			console.error("Failed to mark notification as read:", err);
			return false;
		}
	}, []);

	// Mark all notifications as read via backend API
	const markAllAsRead = useCallback(async () => {
		try {
			const response = await authenticatedFetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/notifications/read-all`,
				{ method: "PATCH" }
			);

			if (!response.ok) {
				const error = await response.json().catch(() => ({ detail: "Failed to mark all as read" }));
				throw new Error(error.detail || "Failed to mark all notifications as read");
			}

			return true;
		} catch (err) {
			console.error("Failed to mark all notifications as read:", err);
			return false;
		}
	}, []);

	// Get unread count
	const unreadCount = notifications.filter((n) => !n.read).length;

	return {
		notifications,
		unreadCount,
		markAsRead,
		markAllAsRead,
		loading,
		error,
	};
}
