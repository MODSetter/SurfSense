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
	const syncKeyRef = useRef<string | null>(null);

	// Start syncing when Electric client is available
	useEffect(() => {
		// Wait for both userId and Electric client to be available
		if (!userId || !electricClient) {
			setLoading(!electricClient); // Still loading if waiting for Electric
			return;
		}

		// Create a unique key for this sync - includes searchSpaceId for proper tracking
		// Note: We sync ALL user notifications but filter by searchSpaceId in queries (memory efficient)
		const syncKey = `notifications_${userId}_space_${searchSpaceId ?? "global"}`;
		if (syncKeyRef.current === syncKey) {
			// Already syncing for this user/searchSpace combo
			return;
		}

		let mounted = true;
		syncKeyRef.current = syncKey;

		async function startSync() {
			try {
				console.log("[useNotifications] Starting sync for user:", userId, "searchSpace:", searchSpaceId);

				// Sync ALL notifications for this user (one subscription for all search spaces)
				// This is memory efficient - we filter by searchSpaceId in queries only
				const handle = await electricClient.syncShape({
					table: "notifications",
					where: `user_id = '${userId}'`,
					primaryKey: ["id"],
				});

				console.log("[useNotifications] Sync started:", {
					isUpToDate: handle.isUpToDate,
					hasStream: !!handle.stream,
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

				// Fetch initial notifications
				await fetchNotifications();

				// Set up live query for real-time updates
				await setupLiveQuery();
			} catch (err) {
				if (!mounted) return;
				console.error("[useNotifications] Failed to start sync:", err);
				setError(err instanceof Error ? err : new Error("Failed to sync notifications"));
				setLoading(false);
			}
		}

		async function fetchNotifications() {
			try {
				// Filter by user_id AND searchSpaceId (or global notifications where search_space_id IS NULL)
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
			} catch (err) {
				console.error("[useNotifications] Failed to fetch:", err);
			}
		}

		async function setupLiveQuery() {
			try {
				// eslint-disable-next-line @typescript-eslint/no-explicit-any
				const db = electricClient.db as any;

				if (db.live?.query && typeof db.live.query === "function") {
					// Filter by user_id AND searchSpaceId (or global notifications)
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

					// Set initial results
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
			} catch (liveErr) {
				console.error("[useNotifications] Failed to set up live query:", liveErr);
			}
		}

		startSync();

		return () => {
			mounted = false;
			syncKeyRef.current = null;
			
			if (syncHandleRef.current) {
				syncHandleRef.current.unsubscribe();
				syncHandleRef.current = null;
			}
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
