"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { DocumentTypeEnum } from "@/contracts/types/document.types";
import { documentsApiService } from "@/lib/apis/documents-api.service";
import type { SyncHandle } from "@/lib/electric/client";
import { useElectricClient } from "@/lib/electric/context";

// Stable empty array to prevent infinite re-renders when no typeFilter is provided
const EMPTY_TYPE_FILTER: DocumentTypeEnum[] = [];

// Document status type (matches backend DocumentStatus JSONB)
export interface DocumentStatusType {
	state: "ready" | "pending" | "processing" | "failed";
	reason?: string;
}

// Document from Electric sync (lightweight table columns - NO content/metadata)
interface DocumentElectric {
	id: number;
	search_space_id: number;
	document_type: string;
	title: string;
	created_by_id: string | null;
	created_at: string;
	status: DocumentStatusType | null;
}

// Document for display (with resolved user name and email)
export interface DocumentDisplay {
	id: number;
	search_space_id: number;
	document_type: string;
	title: string;
	created_by_id: string | null;
	created_by_name: string | null;
	created_by_email: string | null;
	created_at: string;
	status: DocumentStatusType;
}

/**
 * Deduplicate by ID and sort by created_at descending (newest first)
 */
function deduplicateAndSort<T extends { id: number; created_at: string }>(items: T[]): T[] {
	const seen = new Map<number, T>();
	for (const item of items) {
		// Keep the most recent version if duplicate
		const existing = seen.get(item.id);
		if (!existing || new Date(item.created_at) > new Date(existing.created_at)) {
			seen.set(item.id, item);
		}
	}
	return Array.from(seen.values()).sort(
		(a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
	);
}

/**
 * Check if a document has valid/complete data
 */
function isValidDocument(doc: DocumentElectric): boolean {
	return doc.id != null && doc.title != null && doc.title !== "";
}

/**
 * Real-time documents hook with Electric SQL
 *
 * Architecture (100% Reliable):
 * 1. API is the PRIMARY source of truth - always loads first
 * 2. Electric provides REAL-TIME updates for additions and deletions
 * 3. Use syncHandle.isUpToDate to determine if deletions can be trusted
 * 4. Handles bulk deletions correctly by checking sync state
 *
 * Filtering strategy:
 * - Internal state always stores ALL documents (unfiltered)
 * - typeFilter is applied client-side when returning documents
 * - typeCounts always reflect the full dataset so the filter sidebar stays complete
 * - Changing filters is instant (no API re-fetch or Electric re-sync)
 *
 * @param searchSpaceId - The search space ID to filter documents
 * @param typeFilter - Optional document types to filter by (applied client-side)
 */
export function useDocuments(
	searchSpaceId: number | null,
	typeFilter: DocumentTypeEnum[] = EMPTY_TYPE_FILTER
) {
	const electricClient = useElectricClient();

	// Internal state: ALL documents (unfiltered)
	const [allDocuments, setAllDocuments] = useState<DocumentDisplay[]>([]);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<Error | null>(null);

	// Track if initial API load is complete (source of truth)
	const apiLoadedRef = useRef(false);

	// User cache: userId → displayName / email
	const userCacheRef = useRef<Map<string, string>>(new Map());
	const emailCacheRef = useRef<Map<string, string>>(new Map());

	// Electric sync refs
	const syncHandleRef = useRef<SyncHandle | null>(null);
	const liveQueryRef = useRef<{ unsubscribe?: () => void } | null>(null);

	// Type counts from ALL documents (unfiltered) — keeps filter sidebar complete
	const typeCounts = useMemo(() => {
		const counts: Record<string, number> = {};
		for (const doc of allDocuments) {
			counts[doc.document_type] = (counts[doc.document_type] || 0) + 1;
		}
		return counts;
	}, [allDocuments]);

	// Client-side filtered documents for display
	const documents = useMemo(() => {
		if (typeFilter.length === 0) return allDocuments;
		const filterSet = new Set<string>(typeFilter);
		return allDocuments.filter((doc) => filterSet.has(doc.document_type));
	}, [allDocuments, typeFilter]);

	// Populate user cache from API response
	const populateUserCache = useCallback(
		(
			items: Array<{
				created_by_id?: string | null;
				created_by_name?: string | null;
				created_by_email?: string | null;
			}>
		) => {
			for (const item of items) {
				if (item.created_by_id) {
					if (item.created_by_name) {
						userCacheRef.current.set(item.created_by_id, item.created_by_name);
					}
					if (item.created_by_email) {
						emailCacheRef.current.set(item.created_by_id, item.created_by_email);
					}
				}
			}
		},
		[]
	);

	// Convert API item to display doc
	const apiToDisplayDoc = useCallback(
		(item: {
			id: number;
			search_space_id: number;
			document_type: string;
			title: string;
			created_by_id?: string | null;
			created_by_name?: string | null;
			created_by_email?: string | null;
			created_at: string;
			status?: DocumentStatusType | null;
		}): DocumentDisplay => ({
			id: item.id,
			search_space_id: item.search_space_id,
			document_type: item.document_type,
			title: item.title,
			created_by_id: item.created_by_id ?? null,
			created_by_name: item.created_by_name ?? null,
			created_by_email: item.created_by_email ?? null,
			created_at: item.created_at,
			status: item.status ?? { state: "ready" },
		}),
		[]
	);

	// Convert Electric doc to display doc
	const electricToDisplayDoc = useCallback(
		(doc: DocumentElectric): DocumentDisplay => ({
			...doc,
			created_by_name: doc.created_by_id
				? (userCacheRef.current.get(doc.created_by_id) ?? null)
				: null,
			created_by_email: doc.created_by_id
				? (emailCacheRef.current.get(doc.created_by_id) ?? null)
				: null,
			status: doc.status ?? { state: "ready" },
		}),
		[]
	);

	// EFFECT 1: Load ALL documents from API (PRIMARY source of truth)
	// No type filter — always fetches everything so typeCounts stay complete
	useEffect(() => {
		if (!searchSpaceId) {
			setLoading(false);
			return;
		}

		// Capture validated value for async closure
		const spaceId = searchSpaceId;

		let mounted = true;
		apiLoadedRef.current = false;

		async function loadFromApi() {
			try {
				setLoading(true);
				console.log("[useDocuments] Loading from API (source of truth):", spaceId);

				const response = await documentsApiService.getDocuments({
					queryParams: {
						search_space_id: spaceId,
						page: 0,
						page_size: -1, // Fetch all documents (unfiltered)
					},
				});

				if (!mounted) return;

				populateUserCache(response.items);
				const docs = response.items.map(apiToDisplayDoc);
				setAllDocuments(docs);
				apiLoadedRef.current = true;
				setError(null);
				console.log("[useDocuments] API loaded", docs.length, "documents");
			} catch (err) {
				if (!mounted) return;
				console.error("[useDocuments] API load failed:", err);
				setError(err instanceof Error ? err : new Error("Failed to load documents"));
			} finally {
				if (mounted) setLoading(false);
			}
		}

		loadFromApi();

		return () => {
			mounted = false;
		};
	}, [searchSpaceId, populateUserCache, apiToDisplayDoc]);

	// EFFECT 2: Start Electric sync + live query for real-time updates
	// No type filter — syncs and queries ALL documents; filtering is client-side
	useEffect(() => {
		if (!searchSpaceId || !electricClient) return;

		// Capture validated values for async closure
		const spaceId = searchSpaceId;
		const client = electricClient;

		let mounted = true;

		async function setupElectricRealtime() {
			// Cleanup previous subscriptions
			if (syncHandleRef.current) {
				try {
					syncHandleRef.current.unsubscribe();
				} catch {
					// PGlite may already be closed during cleanup
				}
				syncHandleRef.current = null;
			}
			if (liveQueryRef.current) {
				try {
					liveQueryRef.current.unsubscribe?.();
				} catch {
					// PGlite may already be closed during cleanup
				}
				liveQueryRef.current = null;
			}

			try {
				console.log("[useDocuments] Starting Electric sync for real-time updates");

				// Start Electric sync (all documents for this search space)
				const handle = await client.syncShape({
					table: "documents",
					where: `search_space_id = ${spaceId}`,
					columns: [
						"id",
						"document_type",
						"search_space_id",
						"title",
						"created_by_id",
						"created_at",
						"status",
					],
					primaryKey: ["id"],
				});

				if (!mounted) {
					handle.unsubscribe();
					return;
				}

				syncHandleRef.current = handle;
				console.log("[useDocuments] Sync started, isUpToDate:", handle.isUpToDate);

				// Wait for initial sync (with timeout)
				if (!handle.isUpToDate && handle.initialSyncPromise) {
					await Promise.race([
						handle.initialSyncPromise,
						new Promise((resolve) => setTimeout(resolve, 5000)),
					]);
					console.log("[useDocuments] Initial sync complete, isUpToDate:", handle.isUpToDate);
				}

				if (!mounted) return;

				// Set up live query (unfiltered — type filtering is done client-side)
				const db = client.db as {
					live?: {
						query: <T>(
							sql: string,
							params?: (number | string)[]
						) => Promise<{
							subscribe: (cb: (result: { rows: T[] }) => void) => void;
							unsubscribe?: () => void;
						}>;
					};
				};

				if (!db.live?.query) {
					console.warn("[useDocuments] Live queries not available");
					return;
				}

				const query = `SELECT id, document_type, search_space_id, title, created_by_id, created_at, status
					FROM documents 
					WHERE search_space_id = $1
					ORDER BY created_at DESC`;

				const liveQuery = await db.live.query<DocumentElectric>(query, [spaceId]);

				if (!mounted) {
					liveQuery.unsubscribe?.();
					return;
				}

				console.log("[useDocuments] Live query subscribed");

				liveQuery.subscribe((result: { rows: DocumentElectric[] }) => {
					if (!mounted || !result.rows) return;

					// DEBUG: Log first few raw documents to see what's coming from Electric
					console.log("[useDocuments] Raw data sample:", result.rows.slice(0, 3));

					const validItems = result.rows.filter(isValidDocument);
					const isFullySynced = syncHandleRef.current?.isUpToDate ?? false;

					console.log(
						`[useDocuments] Live update: ${result.rows.length} raw, ${validItems.length} valid, synced: ${isFullySynced}`
					);

					// Fetch user names for new users (non-blocking)
					const unknownUserIds = validItems
						.filter(
							(doc): doc is DocumentElectric & { created_by_id: string } =>
								doc.created_by_id !== null && !userCacheRef.current.has(doc.created_by_id)
						)
						.map((doc) => doc.created_by_id);

					if (unknownUserIds.length > 0) {
						documentsApiService
							.getDocuments({
								queryParams: { search_space_id: spaceId, page: 0, page_size: 20 },
							})
							.then((response) => {
								populateUserCache(response.items);
								if (mounted) {
									setAllDocuments((prev) =>
										prev.map((doc) => ({
											...doc,
											created_by_name: doc.created_by_id
												? (userCacheRef.current.get(doc.created_by_id) ?? null)
												: null,
											created_by_email: doc.created_by_id
												? (emailCacheRef.current.get(doc.created_by_id) ?? null)
												: null,
										}))
									);
								}
							})
							.catch(() => {});
					}

					// Smart update logic based on sync state
					setAllDocuments((prev) => {
						// Don't process if API hasn't loaded yet
						if (!apiLoadedRef.current) {
							console.log("[useDocuments] Waiting for API load, skipping live update");
							return prev;
						}

						// Case 1: Live query is empty
						if (validItems.length === 0) {
							if (isFullySynced && prev.length > 0) {
								// Electric is fully synced and says 0 items - trust it (all deleted)
								console.log("[useDocuments] All documents deleted (Electric synced)");
								return [];
							}
							// Partial sync or error - keep existing
							console.log("[useDocuments] Empty live result, keeping existing");
							return prev;
						}

						// Case 2: Electric is fully synced - TRUST IT COMPLETELY (handles bulk deletes)
						if (isFullySynced) {
							const liveDocs = deduplicateAndSort(validItems.map(electricToDisplayDoc));
							console.log(
								`[useDocuments] Synced update: ${liveDocs.length} docs (was ${prev.length})`
							);
							return liveDocs;
						}

						// Case 3: Partial sync - only ADD new items, don't remove any
						const existingIds = new Set(prev.map((d) => d.id));
						const liveIds = new Set(validItems.map((d) => d.id));

						// Find new items (in live but not in prev)
						const newItems = validItems
							.filter((item) => !existingIds.has(item.id))
							.map(electricToDisplayDoc);

						// Find updated items (in both, update with latest data)
						const updatedPrev = prev.map((doc) => {
							if (liveIds.has(doc.id)) {
								const liveItem = validItems.find((v) => v.id === doc.id);
								if (liveItem) {
									return electricToDisplayDoc(liveItem);
								}
							}
							return doc;
						});

						if (newItems.length > 0) {
							console.log(`[useDocuments] Adding ${newItems.length} new items (partial sync)`);
							return deduplicateAndSort([...newItems, ...updatedPrev]);
						}

						return updatedPrev;
					});
				});

				liveQueryRef.current = liveQuery;
			} catch (err) {
				console.error("[useDocuments] Electric setup failed:", err);
				// Don't set error - API data is already loaded
			}
		}

		setupElectricRealtime();

		return () => {
			mounted = false;
			if (syncHandleRef.current) {
				try {
					syncHandleRef.current.unsubscribe();
				} catch {
					// PGlite may already be closed during cleanup
				}
				syncHandleRef.current = null;
			}
			if (liveQueryRef.current) {
				try {
					liveQueryRef.current.unsubscribe?.();
				} catch {
					// PGlite may already be closed during cleanup
				}
				liveQueryRef.current = null;
			}
		};
	}, [searchSpaceId, electricClient, electricToDisplayDoc, populateUserCache]);

	// Track previous searchSpaceId to detect actual changes
	const prevSearchSpaceIdRef = useRef<number | null>(null);

	// Reset on search space change (not on initial mount)
	useEffect(() => {
		if (prevSearchSpaceIdRef.current !== null && prevSearchSpaceIdRef.current !== searchSpaceId) {
			setAllDocuments([]);
			apiLoadedRef.current = false;
			userCacheRef.current.clear();
			emailCacheRef.current.clear();
		}
		prevSearchSpaceIdRef.current = searchSpaceId;
	}, [searchSpaceId]);

	return {
		documents,
		typeCounts,
		total: documents.length,
		loading,
		error,
	};
}
