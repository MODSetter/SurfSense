"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import {
	initElectric,
	isElectricInitialized,
	type ElectricClient,
	type SyncHandle,
} from "@/lib/electric/client";
import type { SearchSourceConnector } from "@/contracts/types/connector.types";

export function useConnectorsElectric(searchSpaceId: number | string | null) {
	const [electric, setElectric] = useState<ElectricClient | null>(null);
	const [connectors, setConnectors] = useState<SearchSourceConnector[]>([]);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<Error | null>(null);
	const syncHandleRef = useRef<SyncHandle | null>(null);
	const liveQueryRef = useRef<{ unsubscribe: () => void } | null>(null);

	// Transform connector data from Electric SQL/PGlite to match expected format
	// Converts Date objects to ISO strings as expected by Zod schema
	function transformConnector(connector: any): SearchSourceConnector {
		return {
			...connector,
			last_indexed_at: connector.last_indexed_at
				? typeof connector.last_indexed_at === "string"
					? connector.last_indexed_at
					: new Date(connector.last_indexed_at).toISOString()
				: null,
			next_scheduled_at: connector.next_scheduled_at
				? typeof connector.next_scheduled_at === "string"
					? connector.next_scheduled_at
					: new Date(connector.next_scheduled_at).toISOString()
				: null,
			created_at: connector.created_at
				? typeof connector.created_at === "string"
					? connector.created_at
					: new Date(connector.created_at).toISOString()
				: new Date().toISOString(), // fallback
		};
	}

	// Initialize Electric SQL and start syncing with real-time updates
	useEffect(() => {
		if (!searchSpaceId) {
			setLoading(false);
			setConnectors([]);
			return;
		}

		let mounted = true;

		async function init() {
			try {
				const electricClient = await initElectric();
				if (!mounted) return;

				setElectric(electricClient);

				// Start syncing connectors for this search space via Electric SQL
				console.log("Starting Electric SQL sync for connectors, search_space_id:", searchSpaceId);

				// Use numeric format for WHERE clause (PGlite sync plugin expects this format)
				const handle = await electricClient.syncShape({
					table: "search_source_connectors",
					where: `search_space_id = ${searchSpaceId}`,
					primaryKey: ["id"],
				});

				console.log("Electric SQL sync started for connectors:", {
					isUpToDate: handle.isUpToDate,
					hasStream: !!handle.stream,
					hasInitialSyncPromise: !!handle.initialSyncPromise,
				});

				// Optimized: Check if already up-to-date before waiting
				if (handle.isUpToDate) {
					console.log("Connectors sync already up-to-date, skipping wait");
				} else if (handle.initialSyncPromise) {
					// Only wait if not already up-to-date
					console.log("Waiting for initial connectors sync to complete...");
					try {
						// Use Promise.race with a shorter timeout to avoid long waits
						await Promise.race([
							handle.initialSyncPromise,
							new Promise((resolve) => setTimeout(resolve, 2000)), // Max 2s wait
						]);
						console.log("Initial connectors sync promise resolved or timed out, checking status:", {
							isUpToDate: handle.isUpToDate,
						});
					} catch (syncErr) {
						console.error("Initial connectors sync failed:", syncErr);
					}
				}

				// Check status after waiting
				console.log("Connectors sync status after waiting:", {
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

				// Fetch connectors after sync is complete (we already waited above)
				await fetchConnectors(electricClient.db);

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
							`SELECT * FROM search_source_connectors WHERE search_space_id = $1 ORDER BY created_at DESC`,
							[searchSpaceId]
						);

						if (!mounted) {
							liveQuery.unsubscribe?.();
							return;
						}

						// Set initial results immediately from the resolved query
						if (liveQuery.initialResults?.rows) {
							console.log(
								"📋 Initial live query results for connectors:",
								liveQuery.initialResults.rows.length
							);
							setConnectors(liveQuery.initialResults.rows.map(transformConnector));
						} else if (liveQuery.rows) {
							// Some versions have rows directly on the result
							console.log(
								"📋 Initial live query results for connectors (direct):",
								liveQuery.rows.length
							);
							setConnectors(liveQuery.rows.map(transformConnector));
						}

						// Subscribe to changes - this is the correct API!
						// The callback fires automatically when Electric SQL syncs new data to PGlite
						if (typeof liveQuery.subscribe === "function") {
							liveQuery.subscribe((result: { rows: any[] }) => {
								if (mounted && result.rows) {
									console.log("🔄 Connectors updated via live query:", result.rows.length);
									setConnectors(result.rows.map(transformConnector));
								}
							});

							// Store unsubscribe function for cleanup
							liveQueryRef.current = liveQuery;
						}
					} else {
						console.warn("PGlite live query API not available, falling back to polling");
					}
				} catch (liveQueryErr) {
					console.error("Failed to set up live query for connectors:", liveQueryErr);
					// Don't fail completely - we still have the initial fetch
				}
			} catch (err) {
				console.error("Failed to initialize Electric SQL for connectors:", err);
				if (mounted) {
					setError(
						err instanceof Error
							? err
							: new Error("Failed to initialize Electric SQL for connectors")
					);
					setLoading(false);
				}
			}
		}

		init();

		return () => {
			mounted = false;
			syncHandleRef.current?.unsubscribe?.();
			liveQueryRef.current?.unsubscribe?.();
			syncHandleRef.current = null;
			liveQueryRef.current = null;
		};
	}, [searchSpaceId]);

	async function fetchConnectors(db: any) {
		try {
			const result = await db.query(
				`SELECT * FROM search_source_connectors WHERE search_space_id = $1 ORDER BY created_at DESC`,
				[searchSpaceId]
			);
			console.log("📋 Fetched connectors from PGlite:", result.rows?.length || 0);
			setConnectors((result.rows || []).map(transformConnector));
		} catch (err) {
			console.error("Failed to fetch connectors from PGlite:", err);
		}
	}

	// Manual refresh function (optional, for fallback)
	const refreshConnectors = useCallback(async () => {
		if (!electric) return;
		await fetchConnectors(electric.db);
	}, [electric]);

	return { connectors, loading, error, refreshConnectors };
}
