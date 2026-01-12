"use client"

import { useEffect, useState, useCallback } from 'react'
import { useLiveQuery } from 'electric-sql/react'
import { initElectric, getElectric, isElectricInitialized } from '@/lib/electric/client'

export interface Notification {
	id: number
	user_id: string
	search_space_id: number | null
	type: string
	title: string
	message: string
	read: boolean
	metadata: Record<string, any>
	created_at: string
	updated_at: string | null
}

export function useNotifications(userId: string | null) {
	const [electric, setElectric] = useState<any>(null)
	const [initialized, setInitialized] = useState(false)
	const [error, setError] = useState<Error | null>(null)

	// Initialize Electric SQL
	useEffect(() => {
		if (!userId || initialized) return

		async function init() {
			try {
				const electricClient = await initElectric()
				setElectric(electricClient)
				setInitialized(true)
				setError(null)
			} catch (err) {
				console.error('Failed to initialize Electric SQL:', err)
				setError(err instanceof Error ? err : new Error('Failed to initialize Electric SQL'))
			}
		}

		init()
	}, [userId, initialized])

	// Use live query to get notifications
	const { results: notifications } = useLiveQuery(
		electric?.db.notifications?.liveMany({
			where: {
				user_id: userId || '',
				read: false,
			},
			orderBy: {
				created_at: 'desc',
			},
		})
	) ?? { results: [] }

	// Mark notification as read
	const markAsRead = useCallback(
		async (notificationId: number) => {
			if (!electric || !isElectricInitialized()) {
				console.warn('Electric SQL not initialized')
				return false
			}

			try {
				await electric.db.notifications.update({
					data: { read: true },
					where: { id: notificationId },
				})
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
			const unread = (notifications || []).filter((n: Notification) => !n.read)
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
	const unreadCount = (notifications || []).filter((n: Notification) => !n.read).length

	return {
		notifications: (notifications || []) as Notification[],
		unreadCount,
		markAsRead,
		markAllAsRead,
		loading: !initialized,
		error,
	}
}

