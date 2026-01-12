/**
 * Electric SQL client setup for ElectricSQL 1.x with PGlite
 * 
 * This uses the new ElectricSQL 1.x architecture:
 * - PGlite: In-browser PostgreSQL database (local storage)
 * - @electric-sql/pglite-sync: Sync plugin to sync Electric shapes into PGlite
 * - @electric-sql/client: HTTP client for subscribing to shapes
 */

import { PGlite } from '@electric-sql/pglite'
import { electricSync } from '@electric-sql/pglite-sync'

// Types
export interface ElectricClient {
	db: PGlite
	syncShape: <T = Record<string, unknown>>(options: SyncShapeOptions) => Promise<SyncHandle<T>>
}

export interface SyncShapeOptions {
	table: string
	where?: string
	columns?: string[]
	primaryKey?: string[]
}

export interface SyncHandle<T = Record<string, unknown>> {
	unsubscribe: () => void
	isUpToDate: boolean
	shape: {
		handle?: string
		offset?: string
	}
}

// Singleton instance
let electricClient: ElectricClient | null = null
let isInitializing = false
let initPromise: Promise<ElectricClient> | null = null

// Get Electric URL from environment
function getElectricUrl(): string {
	if (typeof window !== 'undefined') {
		return process.env.NEXT_PUBLIC_ELECTRIC_URL || 'http://localhost:5133'
	}
	return 'http://localhost:5133'
}

/**
 * Initialize the Electric SQL client with PGlite and sync plugin
 */
export async function initElectric(): Promise<ElectricClient> {
	if (electricClient) {
		return electricClient
	}

	if (isInitializing && initPromise) {
		return initPromise
	}

	isInitializing = true
	initPromise = (async () => {
		try {
			// Create PGlite instance with Electric sync plugin
			const db = await PGlite.create('idb://surfsense-notifications', {
				relaxedDurability: true,
				extensions: {
					electric: electricSync(),
				},
			})

			// Create the notifications table schema in PGlite
			// This matches the backend schema
			await db.exec(`
				CREATE TABLE IF NOT EXISTS notifications (
					id INTEGER PRIMARY KEY,
					user_id TEXT NOT NULL,
					search_space_id INTEGER,
					type TEXT NOT NULL,
					title TEXT NOT NULL,
					message TEXT NOT NULL,
					read BOOLEAN NOT NULL DEFAULT FALSE,
					metadata JSONB DEFAULT '{}',
					created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
					updated_at TIMESTAMPTZ
				);
				
				CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications(user_id);
				CREATE INDEX IF NOT EXISTS idx_notifications_read ON notifications(read);
			`)

			const electricUrl = getElectricUrl()

			// Create the client wrapper
			electricClient = {
				db,
				syncShape: async <T = Record<string, unknown>>(options: SyncShapeOptions): Promise<SyncHandle<T>> => {
					const { table, where, columns, primaryKey = ['id'] } = options

					// Build params for the shape request
					const params: Record<string, string> = { table }
					if (where) params.where = where
					if (columns) params.columns = columns.join(',')

					// Use PGlite's electric sync plugin to sync the shape
					// eslint-disable-next-line @typescript-eslint/no-explicit-any
					const shape = await (db as any).electric.syncShapeToTable({
						shape: {
							url: `${electricUrl}/v1/shape`,
							params,
						},
						table,
						primaryKey,
					})

					return {
						unsubscribe: () => {
							if (shape && typeof shape.unsubscribe === 'function') {
								shape.unsubscribe()
							}
						},
						isUpToDate: shape?.isUpToDate ?? false,
						shape: {
							handle: shape?.handle,
							offset: shape?.offset,
						},
					}
				},
			}

			console.log('Electric SQL initialized successfully with PGlite')
			return electricClient
		} catch (error) {
			console.error('Failed to initialize Electric SQL:', error)
			throw error
		} finally {
			isInitializing = false
		}
	})()

	return initPromise
}

/**
 * Get the Electric client (throws if not initialized)
 */
export function getElectric(): ElectricClient {
	if (!electricClient) {
		throw new Error('Electric not initialized. Call initElectric() first.')
	}
	return electricClient
}

/**
 * Check if Electric is initialized
 */
export function isElectricInitialized(): boolean {
	return electricClient !== null
}

/**
 * Get the PGlite database instance
 */
export function getDb(): PGlite | null {
	return electricClient?.db ?? null
}
