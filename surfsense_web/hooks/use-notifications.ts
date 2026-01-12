"use client"

import { useEffect, useState, useCallback, useRef } from 'react'
import { initElectric, getElectric, isElectricInitialized, type ElectricClient, type SyncHandle } from '@/lib/electric/client'

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
	const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

	// Initialize Electric SQL and start syncing
	useEffect(() => {
		if (!userId || initialized) return

		let mounted = true

		async function init() {
			try {
				const electricClient = await initElectric()
				if (!mounted) return

				setElectric(electricClient)

				// Start syncing notifications for this user
				const handle = await electricClient.syncShape<Notification>({
					table: 'notifications',
					where: `user_id = '${userId}'`,
					primaryKey: ['id'],
				})

				if (!mounted) {
					handle.unsubscribe()
					return
				}

				syncHandleRef.current = handle
				setInitialized(true)
				setError(null)

				// Initial fetch
				await fetchNotifications(electricClient.db)
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
				const result = await db.query<Notification>(
					`SELECT * FROM notifications 
					 WHERE user_id = $1 
					 ORDER BY created_at DESC`,
					[userId]
				)
				if (mounted) {
					setNotifications(result.rows)
				}
			} catch (err) {
				console.error('Failed to fetch notifications:', err)
			}
		}

		init()

		return () => {
			mounted = false
			if (syncHandleRef.current) {
				syncHandleRef.current.unsubscribe()
				syncHandleRef.current = null
			}
		}
	}, [userId, initialized])

	// Poll for updates (PGlite doesn't have live queries like the old electric-sql)
	useEffect(() => {
		if (!electric || !userId || !initialized) return

		const fetchNotifications = async () => {
			try {
				const result = await electric.db.query<Notification>(
					`SELECT * FROM notifications 
					 WHERE user_id = $1 
					 ORDER BY created_at DESC`,
					[userId]
				)
				setNotifications(result.rows)
			} catch (err) {
				console.error('Failed to fetch notifications:', err)
			}
		}

		// Poll every 2 seconds for updates
		pollIntervalRef.current = setInterval(fetchNotifications, 2000)

		return () => {
			if (pollIntervalRef.current) {
				clearInterval(pollIntervalRef.current)
				pollIntervalRef.current = null
			}
		}
	}, [electric, userId, initialized])

	// Mark notification as read (local only - needs backend sync)
	const markAsRead = useCallback(
		async (notificationId: number) => {
			if (!electric || !isElectricInitialized()) {
				console.warn('Electric SQL not initialized')
				return false
			}

			try {
				// Update locally in PGlite
				await electric.db.exec(
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
