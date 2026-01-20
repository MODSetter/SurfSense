"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { SearchSourceConnector } from "@/contracts/types/connector.types";
import type { SyncHandle } from "@/lib/electric/client";
import { useElectricClient } from "@/lib/electric/context";

/**
 * Hook for managing connectors with Electric SQL real-time sync
 *
 * Uses the Electric client from context (provided by ElectricProvider)
 * instead of initializing its own - prevents race conditions and memory leaks
 */
export function useConnectorsElectric(searchSpaceId: number | string | null) {
	// Get Electric client from context - ElectricProvider handles initialization
	const electricClient = useElectricClient();

	const [connectors, setConnectors] = useState<SearchSourceConnector[]>([]);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<Error | null>(null);
	const syncHandleRef = useRef<SyncHandle | null>(null);
	const liveQueryRef = useRef<{ unsubscribe: () => void } | null>(null);
	const syncKeyRef = useRef<string | null>(null);

	// Transform connector data from Electric SQL/PGlite to match expected format
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
				: new Date().toISOString(),
		};
	}

	// Start syncing when Electric client is available
	useEffect(() => {
		// If no Electric client available, immediately mark as not loading (disabled)
		if (!electricClient) {
			setLoading(false);
			setError(new Error("Electric SQL not configured"));
			return;
		}

		// Wait for searchSpaceId to be available
		if (!searchSpaceId) {
			setConnectors([]);
			setLoading(false);
			return;
		}

		// Create a unique key for this sync to prevent duplicate subscriptions
		const syncKey = `connectors_${searchSpaceId}`;
		if (syncKeyRef.current === syncKey) {
			// Already syncing for this search space
			return;
		}

		let mounted = true;
		syncKeyRef.current = syncKey;

		async function startSync() {
			try {
				console.log("[useConnectorsElectric] Starting sync for search space:", searchSpaceId);

				const handle = await electricClient.syncShape({
					table: "search_source_connectors",
					where: `search_space_id = ${searchSpaceId}`,
					primaryKey: ["id"],
				});

				console.log("[useConnectorsElectric] Sync started:", {
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
						console.error("[useConnectorsElectric] Initial sync failed:", syncErr);
					}
				}

				if (!mounted) {
					handle.unsubscribe();
					return;
				}

				syncHandleRef.current = handle;
				setLoading(false);
				setError(null);

				// Fetch initial connectors
				await fetchConnectors();

				// Set up live query for real-time updates
				await setupLiveQuery();
			} catch (err) {
				if (!mounted) return;
				console.error("[useConnectorsElectric] Failed to start sync:", err);
				setError(err instanceof Error ? err : new Error("Failed to sync connectors"));
				setLoading(false);
			}
		}

		async function fetchConnectors() {
			try {
				const result = await electricClient.db.query(
					`SELECT * FROM search_source_connectors WHERE search_space_id = $1 ORDER BY created_at DESC`,
					[searchSpaceId]
				);
				if (mounted) {
					setConnectors((result.rows || []).map(transformConnector));
				}
			} catch (err) {
				console.error("[useConnectorsElectric] Failed to fetch:", err);
			}
		}

		async function setupLiveQuery() {
			try {
				// eslint-disable-next-line @typescript-eslint/no-explicit-any
				const db = electricClient.db as any;

				if (db.live?.query && typeof db.live.query === "function") {
					const liveQuery = await db.live.query(
						`SELECT * FROM search_source_connectors WHERE search_space_id = $1 ORDER BY created_at DESC`,
						[searchSpaceId]
					);

					if (!mounted) {
						liveQuery.unsubscribe?.();
						return;
					}

					// Set initial results
					if (liveQuery.initialResults?.rows) {
						setConnectors(liveQuery.initialResults.rows.map(transformConnector));
					} else if (liveQuery.rows) {
						setConnectors(liveQuery.rows.map(transformConnector));
					}

					// Subscribe to changes
					if (typeof liveQuery.subscribe === "function") {
						liveQuery.subscribe((result: { rows: any[] }) => {
							if (mounted && result.rows) {
								setConnectors(result.rows.map(transformConnector));
							}
						});
					}

					if (typeof liveQuery.unsubscribe === "function") {
						liveQueryRef.current = liveQuery;
					}
				}
			} catch (liveErr) {
				console.error("[useConnectorsElectric] Failed to set up live query:", liveErr);
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
	}, [searchSpaceId, electricClient]);

	// Manual refresh function (optional, for fallback)
	const refreshConnectors = useCallback(async () => {
		if (!electricClient) return;
		try {
			const result = await electricClient.db.query(
				`SELECT * FROM search_source_connectors WHERE search_space_id = $1 ORDER BY created_at DESC`,
				[searchSpaceId]
			);
			setConnectors((result.rows || []).map(transformConnector));
		} catch (err) {
			console.error("[useConnectorsElectric] Failed to refresh:", err);
		}
	}, [electricClient, searchSpaceId]);

	return { connectors, loading, error, refreshConnectors };
}
