"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { SyncHandle } from "@/lib/electric/client";
import { useElectricClient } from "@/lib/electric/context";

interface Document {
	id: number;
	search_space_id: number;
	document_type: string;
	created_at: string;
}

/**
 * Hook for managing documents with Electric SQL real-time sync
 *
 * Uses the Electric client from context (provided by ElectricProvider)
 * instead of initializing its own - prevents race conditions and memory leaks
 */
export function useDocumentsElectric(searchSpaceId: number | string | null) {
	// Get Electric client from context - ElectricProvider handles initialization
	const electricClient = useElectricClient();

	const [documents, setDocuments] = useState<Document[]>([]);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<Error | null>(null);
	const syncHandleRef = useRef<SyncHandle | null>(null);
	const liveQueryRef = useRef<{ unsubscribe: () => void } | null>(null);
	const syncKeyRef = useRef<string | null>(null);

	// Calculate document type counts from synced documents
	const documentTypeCounts = useMemo(() => {
		if (!documents.length) return {};

		const counts: Record<string, number> = {};
		for (const doc of documents) {
			counts[doc.document_type] = (counts[doc.document_type] || 0) + 1;
		}
		return counts;
	}, [documents]);

	// Start syncing when Electric client is available
	useEffect(() => {
		// Wait for both searchSpaceId and Electric client to be available
		if (!searchSpaceId || !electricClient) {
			setLoading(!electricClient); // Still loading if waiting for Electric
			if (!searchSpaceId) {
				setDocuments([]);
			}
			return;
		}

		// Create a unique key for this sync to prevent duplicate subscriptions
		const syncKey = `documents_${searchSpaceId}`;
		if (syncKeyRef.current === syncKey) {
			// Already syncing for this search space
			return;
		}

		let mounted = true;
		syncKeyRef.current = syncKey;

		async function startSync() {
			try {
				console.log("[useDocumentsElectric] Starting sync for search space:", searchSpaceId);

				const handle = await electricClient.syncShape({
					table: "documents",
					where: `search_space_id = ${searchSpaceId}`,
					columns: ["id", "document_type", "search_space_id", "created_at"],
					primaryKey: ["id"],
				});

				console.log("[useDocumentsElectric] Sync started:", {
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
						console.error("[useDocumentsElectric] Initial sync failed:", syncErr);
					}
				}

				if (!mounted) {
					handle.unsubscribe();
					return;
				}

				syncHandleRef.current = handle;
				setLoading(false);
				setError(null);

				// Fetch initial documents
				await fetchDocuments();

				// Set up live query for real-time updates
				await setupLiveQuery();
			} catch (err) {
				if (!mounted) return;
				console.error("[useDocumentsElectric] Failed to start sync:", err);
				setError(err instanceof Error ? err : new Error("Failed to sync documents"));
				setLoading(false);
			}
		}

		async function fetchDocuments() {
			try {
				const result = await electricClient.db.query<Document>(
					`SELECT id, document_type, search_space_id, created_at FROM documents WHERE search_space_id = $1 ORDER BY created_at DESC`,
					[searchSpaceId]
				);
				if (mounted) {
					setDocuments(result.rows || []);
				}
			} catch (err) {
				console.error("[useDocumentsElectric] Failed to fetch:", err);
			}
		}

		async function setupLiveQuery() {
			try {
				// eslint-disable-next-line @typescript-eslint/no-explicit-any
				const db = electricClient.db as any;

				if (db.live?.query && typeof db.live.query === "function") {
					const liveQuery = await db.live.query(
						`SELECT id, document_type, search_space_id, created_at FROM documents WHERE search_space_id = $1 ORDER BY created_at DESC`,
						[searchSpaceId]
					);

					if (!mounted) {
						liveQuery.unsubscribe?.();
						return;
					}

					// Set initial results
					if (liveQuery.initialResults?.rows) {
						setDocuments(liveQuery.initialResults.rows);
					} else if (liveQuery.rows) {
						setDocuments(liveQuery.rows);
					}

					// Subscribe to changes
					if (typeof liveQuery.subscribe === "function") {
						liveQuery.subscribe((result: { rows: Document[] }) => {
							if (mounted && result.rows) {
								setDocuments(result.rows);
							}
						});
					}

					if (typeof liveQuery.unsubscribe === "function") {
						liveQueryRef.current = liveQuery;
					}
				}
			} catch (liveErr) {
				console.error("[useDocumentsElectric] Failed to set up live query:", liveErr);
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

	return { documentTypeCounts, loading, error };
}
