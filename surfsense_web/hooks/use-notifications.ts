"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import {
	initElectric,
	isElectricInitialized,
	type ElectricClient,
	type SyncHandle,
} from "@/lib/electric/client";
import type { Notification } from "@/contracts/types/notification.types";

export type { Notification } from "@/contracts/types/notification.types";

export function useNotifications(userId: string | null) {
	const [electric, setElectric] = useState<ElectricClient | null>(null);
	const [notifications, setNotifications] = useState<Notification[]>([]);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<Error | null>(null);
	const syncHandleRef = useRef<SyncHandle | null>(null);
	const liveQueryRef = useRef<{ unsubscribe: () => void } | null>(null);
	// Use ref instead of state to track initialization - prevents cleanup from running when set
	const initializedRef = useRef(false);

	// Initialize Electric SQL and start syncing with real-time updates
	useEffect(() => {
		// Use ref to prevent re-initialization without triggering cleanup
		if (!userId || initializedRef.current) return;
		initializedRef.current = true;

		let mounted = true;

		async function init() {
			try {
				const electricClient = await initElectric();
				if (!mounted) return;

				setElectric(electricClient);

				// Start syncing notifications for this user via Electric SQL
				// Note: user_id is stored as TEXT in PGlite (UUID from backend is converted)
				console.log("Starting Electric SQL sync for user:", userId);

				// Use string format for WHERE clause (PGlite sync plugin expects this format)
				// The user_id is a UUID string, so we need to quote it properly
				const handle = await electricClient.syncShape({
					table: "notifications",
					where: `user_id = '${userId}'`,
					primaryKey: ["id"],
				});

				console.log("Electric SQL sync started:", {
					isUpToDate: handle.isUpToDate,
					hasStream: !!handle.stream,
					hasInitialSyncPromise: !!handle.initialSyncPromise,
				});

				// Optimized: Check if already up-to-date before waiting
				if (handle.isUpToDate) {
					console.log("Sync already up-to-date, skipping wait");
				} else if (handle.initialSyncPromise) {
					// Only wait if not already up-to-date
					console.log("Waiting for initial sync to complete...");
					try {
						// Use Promise.race with a shorter timeout to avoid long waits
						await Promise.race([
							handle.initialSyncPromise,
							new Promise((resolve) => setTimeout(resolve, 2000)), // Max 2s wait
						]);
						console.log("Initial sync promise resolved or timed out, checking status:", {
							isUpToDate: handle.isUpToDate,
						});
					} catch (syncErr) {
						console.error("Initial sync failed:", syncErr);
					}
				}

				// Check status after waiting
				console.log("Sync status after waiting:", {
					isUpToDate: handle.isUpToDate,
					hasStream: !!handle.stream,
				});

				if (!mounted) {
					handle.unsubscribe();
					return;
				}

				syncHandleRef.current = handle;
				setLoading(false);
				setError(null);

				// Fetch notifications after sync is complete (we already waited above)
				await fetchNotifications(electricClient.db);

				// Set up real-time updates using PGlite live queries
				// Electric SQL syncs data to PGlite in real-time via HTTP streaming
				// PGlite live queries detect when the synced data changes and trigger callbacks
				try {
					// eslint-disable-next-line @typescript-eslint/no-explicit-any
					const db = electricClient.db as any;

					// Use PGlite's live query API for real-time updates
					// CORRECT API: await db.live.query() then use .subscribe()
					if (db.live?.query && typeof db.live.query === "function") {
						// IMPORTANT: db.live.query() returns a Promise - must await it!
						const liveQuery = await db.live.query(
							`SELECT * FROM notifications WHERE user_id = $1 ORDER BY created_at DESC`,
							[userId]
						);

						if (!mounted) {
							liveQuery.unsubscribe?.();
							return;
						}

						// Set initial results immediately from the resolved query
						if (liveQuery.initialResults?.rows) {
							console.log("📋 Initial live query results:", liveQuery.initialResults.rows.length);
							setNotifications(liveQuery.initialResults.rows);
						} else if (liveQuery.rows) {
							// Some versions have rows directly on the result
							console.log("📋 Initial live query results (direct):", liveQuery.rows.length);
							setNotifications(liveQuery.rows);
						}

						// Subscribe to changes - this is the correct API!
						// The callback fires automatically when Electric SQL syncs new data to PGlite
						if (typeof liveQuery.subscribe === "function") {
							liveQuery.subscribe((result: { rows: Notification[] }) => {
								console.log(
									"🔔 Live query update received:",
									result.rows?.length || 0,
									"notifications"
								);
								if (mounted && result.rows) {
									setNotifications(result.rows);
								}
							});
							console.log("✅ Real-time notifications enabled via PGlite live queries");
						} else {
							console.warn("⚠️ Live query subscribe method not available");
						}

						// Store for cleanup
						if (typeof liveQuery.unsubscribe === "function") {
							liveQueryRef.current = liveQuery;
						}
					} else {
						console.error("❌ PGlite live queries not available - db.live.query is not a function");
						console.log("db.live:", db.live);
					}
				} catch (liveErr) {
					console.error("❌ Failed to set up real-time updates:", liveErr);
				}
			} catch (err) {
				if (!mounted) return;
				console.error("Failed to initialize Electric SQL:", err);
				setError(err instanceof Error ? err : new Error("Failed to initialize Electric SQL"));
				// Still mark as loaded so the UI doesn't block
				setLoading(false);
			}
		}

		async function fetchNotifications(
			db: InstanceType<typeof import("@electric-sql/pglite").PGlite>
		) {
			try {
				// Debug: Check all notifications first
				const allNotifications = await db.query<Notification>(
					`SELECT * FROM notifications ORDER BY created_at DESC`
				);
				console.log(
					"All notifications in PGlite:",
					allNotifications.rows?.length || 0,
					allNotifications.rows
				);

				// Use PGlite's query method (not exec for SELECT queries)
				const result = await db.query<Notification>(
					`SELECT * FROM notifications 
					 WHERE user_id = $1 
					 ORDER BY created_at DESC`,
					[userId]
				);
				console.log(`Notifications for user ${userId}:`, result.rows?.length || 0, result.rows);

				if (mounted) {
					// PGlite query returns { rows: [] } format
					setNotifications(result.rows || []);
				}
			} catch (err) {
				console.error("Failed to fetch notifications:", err);
				// Log more details for debugging
				console.error("Error details:", err);
			}
		}

		init();

		return () => {
			mounted = false;
			// Reset initialization state so we can reinitialize with a new userId
			initializedRef.current = false;
			setLoading(true);
			if (syncHandleRef.current) {
				syncHandleRef.current.unsubscribe();
				syncHandleRef.current = null;
			}
			if (liveQueryRef.current) {
				liveQueryRef.current.unsubscribe();
				liveQueryRef.current = null;
			}
		};
		// Only depend on userId - using ref for initialization tracking to prevent cleanup issues
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [userId]);

	// Mark notification as read (local only - needs backend sync)
	const markAsRead = useCallback(
		async (notificationId: number) => {
			if (!electric || !isElectricInitialized()) {
				console.warn("Electric SQL not initialized");
				return false;
			}

			try {
				// Update locally in PGlite
				await electric.db.query(
					`UPDATE notifications SET read = true, updated_at = NOW() WHERE id = $1`,
					[notificationId]
				);

				// Update local state
				setNotifications((prev) =>
					prev.map((n) => (n.id === notificationId ? { ...n, read: true } : n))
				);

				// TODO: Also send to backend to persist the change
				// This could be done via a REST API call

				return true;
			} catch (err) {
				console.error("Failed to mark notification as read:", err);
				return false;
			}
		},
		[electric]
	);

	// Mark all notifications as read
	const markAllAsRead = useCallback(async () => {
		if (!electric || !isElectricInitialized()) {
			console.warn("Electric SQL not initialized");
			return false;
		}

		try {
			const unread = notifications.filter((n) => !n.read);
			for (const notification of unread) {
				await markAsRead(notification.id);
			}
			return true;
		} catch (err) {
			console.error("Failed to mark all notifications as read:", err);
			return false;
		}
	}, [electric, notifications, markAsRead]);

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
