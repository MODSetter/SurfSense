"use client"

import { useEffect, useState, useCallback, useRef } from 'react'
import { initElectric, isElectricInitialized, type ElectricClient, type SyncHandle } from '@/lib/electric/client'

export interface Notification {
	id: number
	user_id: string
	search_space_id: number | null
	type: string
	title: string
	message: string
	read: boolean
	metadata: Record<string, unknown>
	created_at: string
	updated_at: string | null
}

export function useNotifications(userId: string | null) {
	const [electric, setElectric] = useState<ElectricClient | null>(null)
	const [notifications, setNotifications] = useState<Notification[]>([])
	const [initialized, setInitialized] = useState(false)
	const [error, setError] = useState<Error | null>(null)
	const syncHandleRef = useRef<SyncHandle | null>(null)
	const liveQueryRef = useRef<{ unsubscribe: () => void } | null>(null)

	// Initialize Electric SQL and start syncing with real-time updates
	useEffect(() => {
		if (!userId || initialized) return

		let mounted = true

		async function init() {
			try {
				const electricClient = await initElectric()
				if (!mounted) return

				setElectric(electricClient)

				// Start syncing notifications for this user via Electric SQL
				// Note: user_id is stored as TEXT in PGlite (UUID from backend is converted)
				console.log('Starting Electric SQL sync for user:', userId)
				
				// Use string format for WHERE clause (PGlite sync plugin expects this format)
				// The user_id is a UUID string, so we need to quote it properly
				const handle = await electricClient.syncShape({
					table: 'notifications',
					where: `user_id = '${userId}'`,
					primaryKey: ['id'],
				})
				
				console.log('Electric SQL sync started:', {
					isUpToDate: handle.isUpToDate,
					hasStream: !!handle.stream,
					hasInitialSyncPromise: !!handle.initialSyncPromise,
				})
				
				// Wait for initial sync to complete if the promise is available
				if (handle.initialSyncPromise) {
					console.log('Waiting for initial sync to complete...')
					try {
						await handle.initialSyncPromise
						console.log('Initial sync promise resolved, checking status:', {
							isUpToDate: handle.isUpToDate,
						})
					} catch (syncErr) {
						console.error('Initial sync failed:', syncErr)
					}
				}
				
				// Check status after waiting
				console.log('Sync status after waiting:', {
					isUpToDate: handle.isUpToDate,
					hasStream: !!handle.stream,
				})

				if (!mounted) {
					handle.unsubscribe()
					return
				}

				syncHandleRef.current = handle
				setInitialized(true)
				setError(null)

				// Fetch notifications after sync is complete (we already waited above)
				await fetchNotifications(electricClient.db)

				// Set up real-time updates using PGlite live queries
				// Electric SQL syncs data to PGlite in real-time via WebSocket/HTTP
				// PGlite live queries detect when the synced data changes and trigger callbacks
				try {
					// eslint-disable-next-line @typescript-eslint/no-explicit-any
					const db = electricClient.db as any
					
					// Use PGlite's live query API for real-time updates
					// Based on latest PGlite docs: db.live.query(query, params, callback)
					if (db.live?.query && typeof db.live.query === 'function') {
						const liveQuery = db.live.query(
							`SELECT * FROM notifications WHERE user_id = $1 ORDER BY created_at DESC`,
							[userId],
							(result: { rows: Notification[] }) => {
								// This callback fires automatically when Electric SQL syncs changes
								if (mounted) {
									setNotifications(result.rows)
								}
							}
						)
						
						// Set initial results immediately
						if (liveQuery.initialResults) {
							setNotifications(liveQuery.initialResults.rows)
						}
						
						if (mounted && liveQuery && typeof liveQuery.unsubscribe === 'function') {
							liveQueryRef.current = liveQuery
							console.log('✅ Real-time notifications enabled via PGlite live queries')
						}
					} else {
						// Fallback: Monitor sync handle for updates
						// Electric SQL's syncShape should trigger updates, but we need to detect them
						// This is a lightweight approach that only checks when sync indicates changes
						console.warn('PGlite live queries not available - using sync-based change detection')
						
						let lastNotificationIds = new Set<number>()
						
						const checkForSyncUpdates = async () => {
							if (!mounted) return
							
							try {
								const result = await electricClient.db.query<Notification>(
									`SELECT * FROM notifications WHERE user_id = $1 ORDER BY created_at DESC`,
									[userId]
								)
								
								// PGlite query returns { rows: [] } format
								const rows = result.rows || []
								
								// Only update if data actually changed
								const currentIds = new Set(rows.map(r => r.id))
								const currentHash = JSON.stringify(
									rows.map(r => ({ id: r.id, read: r.read, updated_at: r.updated_at }))
								)
								
								// Check if IDs changed (new/deleted notifications)
								const idsChanged = 
									currentIds.size !== lastNotificationIds.size ||
									[...currentIds].some(id => !lastNotificationIds.has(id)) ||
									[...lastNotificationIds].some(id => !currentIds.has(id))
								
								if (idsChanged) {
									setNotifications(rows)
									lastNotificationIds = currentIds
								} else {
									// Check if any notification properties changed (e.g., read status)
									// Compare with current state
									setNotifications(prev => {
										const prevHash = JSON.stringify(
											prev.map(r => ({ id: r.id, read: r.read, updated_at: r.updated_at }))
										)
										if (prevHash !== currentHash) {
											return rows
										}
										return prev
									})
								}
							} catch (err) {
								console.error('Failed to check for notification updates:', err)
							}
							
							// Check again after a short delay (Electric SQL syncs are fast)
							if (mounted) {
								setTimeout(checkForSyncUpdates, 500) // Check every 500ms - Electric SQL syncs are near-instant
							}
						}
						
						// Start monitoring
						checkForSyncUpdates()
						
						liveQueryRef.current = {
							unsubscribe: () => {
								mounted = false
							}
						}
					}
				} catch (liveErr) {
					console.warn('Failed to set up real-time updates:', liveErr)
					// Minimal fallback - this should rarely be needed
					liveQueryRef.current = {
						unsubscribe: () => {}
					}
				}
			} catch (err) {
				if (!mounted) return
				console.error('Failed to initialize Electric SQL:', err)
				setError(err instanceof Error ? err : new Error('Failed to initialize Electric SQL'))
				// Still mark as initialized so the UI doesn't block
				setInitialized(true)
			}
		}

		async function fetchNotifications(db: InstanceType<typeof import('@electric-sql/pglite').PGlite>) {
			try {
				// Debug: Check all notifications first
				const allNotifications = await db.query<Notification>(
					`SELECT * FROM notifications ORDER BY created_at DESC`
				)
				console.log('All notifications in PGlite:', allNotifications.rows?.length || 0, allNotifications.rows)
				
				// Use PGlite's query method (not exec for SELECT queries)
				const result = await db.query<Notification>(
					`SELECT * FROM notifications 
					 WHERE user_id = $1 
					 ORDER BY created_at DESC`,
					[userId]
				)
				console.log(`Notifications for user ${userId}:`, result.rows?.length || 0, result.rows)
				
				if (mounted) {
					// PGlite query returns { rows: [] } format
					setNotifications(result.rows || [])
				}
			} catch (err) {
				console.error('Failed to fetch notifications:', err)
				// Log more details for debugging
				console.error('Error details:', err)
			}
		}

		init()

		return () => {
			mounted = false
			if (syncHandleRef.current) {
				syncHandleRef.current.unsubscribe()
				syncHandleRef.current = null
			}
			if (liveQueryRef.current) {
				liveQueryRef.current.unsubscribe()
				liveQueryRef.current = null
			}
		}
	}, [userId, initialized])

	// Mark notification as read (local only - needs backend sync)
	const markAsRead = useCallback(
		async (notificationId: number) => {
			if (!electric || !isElectricInitialized()) {
				console.warn('Electric SQL not initialized')
				return false
			}

			try {
				// Update locally in PGlite
				await electric.db.query(
					`UPDATE notifications SET read = true, updated_at = NOW() WHERE id = $1`,
					[notificationId]
				)

				// Update local state
				setNotifications(prev =>
					prev.map(n => n.id === notificationId ? { ...n, read: true } : n)
				)

				// TODO: Also send to backend to persist the change
				// This could be done via a REST API call

				return true
			} catch (err) {
				console.error('Failed to mark notification as read:', err)
				return false
			}
		},
		[electric]
	)

	// Mark all notifications as read
	const markAllAsRead = useCallback(async () => {
		if (!electric || !isElectricInitialized()) {
			console.warn('Electric SQL not initialized')
			return false
		}

		try {
			const unread = notifications.filter(n => !n.read)
			for (const notification of unread) {
				await markAsRead(notification.id)
			}
			return true
		} catch (err) {
			console.error('Failed to mark all notifications as read:', err)
			return false
		}
	}, [electric, notifications, markAsRead])

	// Get unread count
	const unreadCount = notifications.filter(n => !n.read).length

	return {
		notifications,
		unreadCount,
		markAsRead,
		markAllAsRead,
		loading: !initialized,
		error,
	}
}
