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
import { live } from '@electric-sql/pglite/live'

// Types
export interface ElectricClient {
	db: PGlite
	syncShape: (options: SyncShapeOptions) => Promise<SyncHandle>
}

export interface SyncShapeOptions {
	table: string
	where?: string
	columns?: string[]
	primaryKey?: string[]
}

export interface SyncHandle {
	unsubscribe: () => void
	readonly isUpToDate: boolean
	// The stream property contains the ShapeStreamInterface from pglite-sync
	stream?: unknown
	// Promise that resolves when initial sync is complete
	initialSyncPromise?: Promise<void>
}

// Singleton instance
let electricClient: ElectricClient | null = null
let isInitializing = false
let initPromise: Promise<ElectricClient> | null = null

// Version for sync state - increment this to force fresh sync when Electric config changes
// Incremented to v4 to fix sync completion issues
const SYNC_VERSION = 4

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
			// Create PGlite instance with Electric sync plugin and live queries
			// Include version in database name to force fresh sync when Electric config changes
			const db = await PGlite.create({
				dataDir: `idb://surfsense-notifications-v${SYNC_VERSION}`,
				relaxedDurability: true,
				extensions: {
					// Enable debug mode in electricSync to see detailed sync logs
					electric: electricSync({ debug: true }),
					live, // Enable live queries for real-time updates
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
				syncShape: async (options: SyncShapeOptions): Promise<SyncHandle> => {
					const { table, where, columns, primaryKey = ['id'] } = options

				// Build params for the shape request
				// Electric SQL expects params as URL query parameters
				const params: Record<string, string> = { table }
				
				// Validate and fix WHERE clause to ensure string literals are properly quoted
				let validatedWhere = where
				if (where) {
					// Check if where uses positional parameters
					if (where.includes('$1')) {
						// Extract the value from the where clause if it's embedded
						// For now, we'll use the where clause as-is and let Electric handle it
						params.where = where
						validatedWhere = where
					} else {
						// Validate that string literals are properly quoted
						// Count single quotes - should be even (pairs) for properly quoted strings
						const singleQuoteCount = (where.match(/'/g) || []).length
						
						if (singleQuoteCount % 2 !== 0) {
							// Odd number of quotes means unterminated string literal
							console.warn('Where clause has unmatched quotes, fixing:', where)
							// Add closing quote at the end
							validatedWhere = `${where}'`
							params.where = validatedWhere
						} else {
							// Use the where clause directly (already formatted)
							params.where = where
							validatedWhere = where
						}
					}
				}
				
				if (columns) params.columns = columns.join(',')

					console.log('Syncing shape with params:', params)
					console.log('Electric URL:', `${electricUrl}/v1/shape`)
					console.log('Where clause:', where, 'Validated:', validatedWhere)

					try {
						// Debug: Test Electric SQL connection directly first
						// Use validatedWhere to ensure proper URL encoding
						const testUrl = `${electricUrl}/v1/shape?table=${table}&offset=-1${validatedWhere ? `&where=${encodeURIComponent(validatedWhere)}` : ''}`
						console.log('Testing Electric SQL directly:', testUrl)
						try {
							const testResponse = await fetch(testUrl)
							const testHeaders = {
								handle: testResponse.headers.get('electric-handle'),
								offset: testResponse.headers.get('electric-offset'),
								upToDate: testResponse.headers.get('electric-up-to-date'),
							}
							console.log('Direct Electric SQL response headers:', testHeaders)
							const testData = await testResponse.json()
							console.log('Direct Electric SQL data count:', Array.isArray(testData) ? testData.length : 'not array', testData)
						} catch (testErr) {
							console.error('Direct Electric SQL test failed:', testErr)
						}

						// Use PGlite's electric sync plugin to sync the shape
					// According to Electric SQL docs, the shape config uses params for table, where, columns
					// Note: mapColumns is OPTIONAL per pglite-sync types.ts
					
					// Create a promise that resolves when initial sync is complete
					let resolveInitialSync: () => void
					let rejectInitialSync: (error: Error) => void
					const initialSyncPromise = new Promise<void>((resolve, reject) => {
						resolveInitialSync = resolve
						rejectInitialSync = reject
						// Safety timeout - if sync doesn't complete in 30s, something is wrong
						setTimeout(() => {
							console.warn(`⚠️ Sync timeout for ${table} - sync did not complete in 30s`)
							resolve() // Resolve anyway to not block, but log warning
						}, 30000)
					})
					
					const shapeConfig = {
						shape: {
							url: `${electricUrl}/v1/shape`,
							params: {
								table,
								...(validatedWhere ? { where: validatedWhere } : {}),
								...(columns ? { columns: columns.join(',') } : {}),
							},
						},
						table,
						primaryKey,
						shapeKey: `v${SYNC_VERSION}_${table}_${where?.replace(/[^a-zA-Z0-9]/g, '_') || 'all'}`, // Versioned key to force fresh sync when needed
						onInitialSync: () => {
							console.log(`✅ Initial sync complete for ${table} - data should now be in PGlite`)
							resolveInitialSync()
						},
						onError: (error: Error) => {
							console.error(`❌ Shape sync error for ${table}:`, error)
							console.error('Error details:', JSON.stringify(error, Object.getOwnPropertyNames(error)))
							rejectInitialSync(error)
						},
					}
					
					console.log('syncShapeToTable config:', JSON.stringify(shapeConfig, null, 2))
					
					// Type assertion to PGlite with electric extension
					const pgWithElectric = db as PGlite & { electric: { syncShapeToTable: (config: typeof shapeConfig) => Promise<{ unsubscribe: () => void; isUpToDate: boolean; stream: unknown }> } }
					const shape = await pgWithElectric.electric.syncShapeToTable(shapeConfig)

					if (!shape) {
						throw new Error('syncShapeToTable returned undefined')
					}

					// Log the actual shape result structure
					console.log('Shape sync result (initial):', {
						hasUnsubscribe: typeof shape?.unsubscribe === 'function',
						isUpToDate: shape?.isUpToDate,
						hasStream: !!shape?.stream,
						streamType: typeof shape?.stream,
					})
					
					// Debug the stream if available
					if (shape?.stream) {
						const stream = shape.stream as any
						console.log('Shape stream details:', {
							shapeHandle: stream?.shapeHandle,
							lastOffset: stream?.lastOffset,
							isUpToDate: stream?.isUpToDate,
							error: stream?.error,
							hasSubscribe: typeof stream?.subscribe === 'function',
							hasUnsubscribe: typeof stream?.unsubscribe === 'function',
						})
						
						// Try to subscribe to the stream to see if it's receiving messages
						if (typeof stream?.subscribe === 'function') {
							console.log('Subscribing to shape stream for debugging...')
							stream.subscribe((messages: unknown[]) => {
								console.log('🔵 Shape stream received messages:', messages?.length || 0)
								if (messages && messages.length > 0) {
									console.log('First message:', JSON.stringify(messages[0], null, 2))
								}
							})
						}
					}
					
					// Wait briefly to see if sync starts
					await new Promise(resolve => setTimeout(resolve, 100))
					console.log('Shape sync result (after 100ms):', {
						isUpToDate: shape?.isUpToDate,
					})

					// Return the shape handle - isUpToDate is a getter that reflects current state
					return {
						unsubscribe: () => {
							console.log('unsubscribing')
							if (shape && typeof shape.unsubscribe === 'function') {
								shape.unsubscribe()
							}
						},
						// Use getter to always return current state
						get isUpToDate() {
							return shape?.isUpToDate ?? false
						},
						stream: shape?.stream,
						initialSyncPromise, // Expose promise so callers can wait for sync
					}
					} catch (error) {
						console.error('Failed to sync shape:', error)
						// Check if Electric SQL server is reachable
						try {
							const response = await fetch(`${electricUrl}/v1/shape?table=${table}&offset=-1`, {
								method: 'GET',
							})
							console.log('Electric SQL server response:', response.status, response.statusText)
							if (!response.ok) {
								console.error('Electric SQL server error:', await response.text())
							}
						} catch (fetchError) {
							console.error('Cannot reach Electric SQL server:', fetchError)
							console.error('Make sure Electric SQL is running at:', electricUrl)
						}
						throw error
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
