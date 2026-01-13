"use client"

import { useEffect, useState, useRef, useMemo } from 'react'
import { initElectric, type ElectricClient, type SyncHandle } from '@/lib/electric/client'

interface Document {
	id: number
	search_space_id: number
	document_type: string
	created_at: string
}

export function useDocumentsElectric(searchSpaceId: number | string | null) {
	const [electric, setElectric] = useState<ElectricClient | null>(null)
	const [documents, setDocuments] = useState<Document[]>([])
	const [loading, setLoading] = useState(true)
	const [error, setError] = useState<Error | null>(null)
	const syncHandleRef = useRef<SyncHandle | null>(null)
	const liveQueryRef = useRef<{ unsubscribe: () => void } | null>(null)

	// Calculate document type counts from synced documents
	const documentTypeCounts = useMemo(() => {
		if (!documents.length) return {}
		
		const counts: Record<string, number> = {}
		for (const doc of documents) {
			counts[doc.document_type] = (counts[doc.document_type] || 0) + 1
		}
		return counts
	}, [documents])

	// Initialize Electric SQL and start syncing with real-time updates
	useEffect(() => {
		if (!searchSpaceId) {
			setLoading(false)
			setDocuments([])
			return
		}

		let mounted = true

		async function init() {
			try {
				const electricClient = await initElectric()
				if (!mounted) return

				setElectric(electricClient)

				// Start syncing documents for this search space via Electric SQL
				// Only sync id, document_type, search_space_id columns for efficiency
				console.log('Starting Electric SQL sync for documents, search_space_id:', searchSpaceId)
				
				const handle = await electricClient.syncShape({
					table: 'documents',
					where: `search_space_id = ${searchSpaceId}`,
					columns: ['id', 'document_type', 'search_space_id', 'created_at'],
					primaryKey: ['id'],
				})
				
				console.log('Electric SQL sync started for documents:', {
					isUpToDate: handle.isUpToDate,
					hasStream: !!handle.stream,
					hasInitialSyncPromise: !!handle.initialSyncPromise,
				})
				
				// Optimized: Check if already up-to-date before waiting
				if (handle.isUpToDate) {
					console.log('Documents sync already up-to-date, skipping wait')
				} else if (handle.initialSyncPromise) {
					// Only wait if not already up-to-date
					console.log('Waiting for initial documents sync to complete...')
					try {
						// Use Promise.race with a shorter timeout to avoid long waits
						await Promise.race([
							handle.initialSyncPromise,
							new Promise(resolve => setTimeout(resolve, 2000)), // Max 2s wait
						])
						console.log('Initial documents sync promise resolved or timed out, checking status:', {
							isUpToDate: handle.isUpToDate,
						})
					} catch (syncErr) {
						console.error('Initial documents sync failed:', syncErr)
					}
				}
				
				// Check status after waiting
				console.log('Documents sync status after waiting:', {
					isUpToDate: handle.isUpToDate,
					hasStream: !!handle.stream,
				})

				if (!mounted) {
					handle.unsubscribe()
					return
				}

				syncHandleRef.current = handle
				setLoading(false)
				setError(null)

				// Fetch documents after sync is complete (we already waited above)
				await fetchDocuments(electricClient.db)

				// Set up real-time updates using PGlite live queries
				// Electric SQL syncs data to PGlite in real-time via HTTP streaming
				// PGlite live queries detect when the synced data changes and trigger callbacks
				try {
					// eslint-disable-next-line @typescript-eslint/no-explicit-any
					const db = electricClient.db as any
					
					// Use PGlite's live query API for real-time updates
					// CORRECT API: await db.live.query() then use .subscribe()
					if (db.live?.query && typeof db.live.query === 'function') {
						// IMPORTANT: db.live.query() returns a Promise - must await it!
						const liveQuery = await db.live.query(
							`SELECT id, document_type, search_space_id, created_at FROM documents WHERE search_space_id = $1 ORDER BY created_at DESC`,
							[searchSpaceId]
						)
						
						if (!mounted) {
							liveQuery.unsubscribe?.()
							return
						}
						
						// Set initial results immediately from the resolved query
						if (liveQuery.initialResults?.rows) {
							console.log('📋 Initial live query results for documents:', liveQuery.initialResults.rows.length)
							setDocuments(liveQuery.initialResults.rows)
						} else if (liveQuery.rows) {
							// Some versions have rows directly on the result
							console.log('📋 Initial live query results for documents (direct):', liveQuery.rows.length)
							setDocuments(liveQuery.rows)
						}
						
						// Subscribe to changes - this is the correct API!
						// The callback fires automatically when Electric SQL syncs new data to PGlite
						if (typeof liveQuery.subscribe === 'function') {
							liveQuery.subscribe((result: { rows: Document[] }) => {
								if (mounted && result.rows) {
									console.log('🔄 Documents updated via live query:', result.rows.length)
									setDocuments(result.rows)
								}
							})
							
							// Store unsubscribe function for cleanup
							liveQueryRef.current = liveQuery
						}
					} else {
						console.warn('PGlite live query API not available for documents, falling back to polling')
					}
				} catch (liveQueryErr) {
					console.error('Failed to set up live query for documents:', liveQueryErr)
					// Don't fail completely - we still have the initial fetch
				}
			} catch (err) {
				console.error('Failed to initialize Electric SQL for documents:', err)
				if (mounted) {
					setError(err instanceof Error ? err : new Error('Failed to initialize Electric SQL for documents'))
					setLoading(false)
				}
			}
		}

		init()

		return () => {
			mounted = false
			syncHandleRef.current?.unsubscribe?.()
			liveQueryRef.current?.unsubscribe?.()
			syncHandleRef.current = null
			liveQueryRef.current = null
		}
	}, [searchSpaceId])

	async function fetchDocuments(db: any) {
		try {
			const result = await db.query(
				`SELECT id, document_type, search_space_id, created_at FROM documents WHERE search_space_id = $1 ORDER BY created_at DESC`,
				[searchSpaceId]
			)
			console.log('📋 Fetched documents from PGlite:', result.rows?.length || 0)
			setDocuments(result.rows || [])
		} catch (err) {
			console.error('Failed to fetch documents from PGlite:', err)
		}
	}

	return { documentTypeCounts, loading, error }
}

