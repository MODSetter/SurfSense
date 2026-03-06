"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type {
	DocumentSortBy,
	DocumentTypeEnum,
	SortOrder,
} from "@/contracts/types/document.types";
import { documentsApiService } from "@/lib/apis/documents-api.service";
import type { SyncHandle } from "@/lib/electric/client";
import { useElectricClient } from "@/lib/electric/context";

export interface DocumentStatusType {
	state: "ready" | "pending" | "processing" | "failed";
	reason?: string;
}

interface DocumentElectric {
	id: number;
	search_space_id: number;
	document_type: string;
	title: string;
	created_by_id: string | null;
	created_at: string;
	status: DocumentStatusType | null;
}

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

const EMPTY_TYPE_FILTER: DocumentTypeEnum[] = [];
const INITIAL_PAGE_SIZE = 20;
const SCROLL_PAGE_SIZE = 5;

function isValidDocument(doc: DocumentElectric): boolean {
	return doc.id != null && doc.title != null && doc.title !== "";
}

/**
 * Paginated documents hook with Electric SQL real-time updates.
 *
 * Architecture:
 * 1. API is the PRIMARY data source — fetches pages on demand
 * 2. Type counts come from a dedicated lightweight API endpoint
 * 3. Electric provides REAL-TIME updates (new docs, deletions, status changes)
 * 4. Server-side sorting via sort_by + sort_order params
 *
 * @param searchSpaceId - The search space to load documents for
 * @param typeFilter - Document types to filter by (server-side)
 * @param sortBy - Column to sort by (server-side)
 * @param sortOrder - Sort direction (server-side)
 */
export function useDocuments(
	searchSpaceId: number | null,
	typeFilter: DocumentTypeEnum[] = EMPTY_TYPE_FILTER,
	sortBy: DocumentSortBy = "created_at",
	sortOrder: SortOrder = "desc"
) {
	const electricClient = useElectricClient();

	const [documents, setDocuments] = useState<DocumentDisplay[]>([]);
	const [typeCounts, setTypeCounts] = useState<Record<string, number>>({});
	const [total, setTotal] = useState(0);
	const [loading, setLoading] = useState(true);
	const [loadingMore, setLoadingMore] = useState(false);
	const [hasMore, setHasMore] = useState(false);
	const [error, setError] = useState<Error | null>(null);

	const apiLoadedCountRef = useRef(0);
	const initialLoadDoneRef = useRef(false);
	const prevParamsRef = useRef<{ sortBy: string; sortOrder: string; typeFilterKey: string } | null>(null);
	// Snapshot of all doc IDs from Electric's first callback after initial load.
	// Anything appearing in subsequent callbacks NOT in this set is genuinely new.
	const electricBaselineIdsRef = useRef<Set<number> | null>(null);
	const knownApiIdsRef = useRef<Set<number>>(new Set());
	const userCacheRef = useRef<Map<string, string>>(new Map());
	const emailCacheRef = useRef<Map<string, string>>(new Map());
	const syncHandleRef = useRef<SyncHandle | null>(null);
	const liveQueryRef = useRef<{ unsubscribe?: () => void } | null>(null);

	const typeFilterKey = typeFilter.join(",");

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

	// EFFECT 1: Fetch first page + type counts when params change
	// biome-ignore lint/correctness/useExhaustiveDependencies: typeFilterKey serializes typeFilter
	useEffect(() => {
		if (!searchSpaceId) return;

		let cancelled = false;

		const prev = prevParamsRef.current;
		const isSortOnlyChange =
			initialLoadDoneRef.current &&
			prev !== null &&
			prev.typeFilterKey === typeFilterKey &&
			(prev.sortBy !== sortBy || prev.sortOrder !== sortOrder);
		prevParamsRef.current = { sortBy, sortOrder, typeFilterKey };

		if (!isSortOnlyChange) {
			setLoading(true);
			setDocuments([]);
			setTotal(0);
			setHasMore(false);
		}
		apiLoadedCountRef.current = 0;
		initialLoadDoneRef.current = false;
		electricBaselineIdsRef.current = null;
		knownApiIdsRef.current = new Set();

		const fetchInitialData = async () => {
			try {
				const [docsResponse, countsResponse] = await Promise.all([
					documentsApiService.getDocuments({
						queryParams: {
							search_space_id: searchSpaceId,
							page: 0,
							page_size: INITIAL_PAGE_SIZE,
							...(typeFilter.length > 0 && { document_types: typeFilter }),
							sort_by: sortBy,
							sort_order: sortOrder,
						},
					}),
					documentsApiService.getDocumentTypeCounts({
						queryParams: { search_space_id: searchSpaceId },
					}),
				]);

				if (cancelled) return;

				populateUserCache(docsResponse.items);
				const docs = docsResponse.items.map(apiToDisplayDoc);
				setDocuments(docs);
				setTotal(docsResponse.total);
				setHasMore(docsResponse.has_more);
				setTypeCounts(countsResponse);
				setError(null);
				apiLoadedCountRef.current = docsResponse.items.length;
				initialLoadDoneRef.current = true;
				for (const doc of docs) {
					knownApiIdsRef.current.add(doc.id);
				}
			} catch (err) {
				if (cancelled) return;
				console.error("[useDocuments] Initial load failed:", err);
				setError(
					err instanceof Error ? err : new Error("Failed to load documents")
				);
			} finally {
				if (!cancelled) setLoading(false);
			}
		};

		fetchInitialData();
		return () => {
			cancelled = true;
		};
	}, [searchSpaceId, typeFilterKey, sortBy, sortOrder, populateUserCache, apiToDisplayDoc]);

	// EFFECT 2: Electric sync + live query for real-time updates
	useEffect(() => {
		if (!searchSpaceId || !electricClient) return;

		const spaceId = searchSpaceId;
		const client = electricClient;
		let mounted = true;

		async function setupElectricRealtime() {
			if (syncHandleRef.current) {
				try {
					syncHandleRef.current.unsubscribe();
				} catch {
					/* PGlite may already be closed */
				}
				syncHandleRef.current = null;
			}
			if (liveQueryRef.current) {
				try {
					liveQueryRef.current.unsubscribe?.();
				} catch {
					/* PGlite may already be closed */
				}
				liveQueryRef.current = null;
			}

			try {
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

				if (!handle.isUpToDate && handle.initialSyncPromise) {
					await Promise.race([
						handle.initialSyncPromise,
						new Promise((resolve) => setTimeout(resolve, 5000)),
					]);
				}

				if (!mounted) return;

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

				if (!db.live?.query) return;

				const query = `SELECT id, document_type, search_space_id, title, created_by_id, created_at, status
					FROM documents
					WHERE search_space_id = $1
					ORDER BY created_at DESC`;

				const liveQuery = await db.live.query<DocumentElectric>(query, [
					spaceId,
				]);

				if (!mounted) {
					liveQuery.unsubscribe?.();
					return;
				}

				liveQuery.subscribe((result: { rows: DocumentElectric[] }) => {
					if (!mounted || !result.rows || !initialLoadDoneRef.current) return;

					const validItems = result.rows.filter(isValidDocument);
					const isFullySynced = syncHandleRef.current?.isUpToDate ?? false;

					const unknownUserIds = validItems
						.filter(
							(
								doc
							): doc is DocumentElectric & { created_by_id: string } =>
								doc.created_by_id !== null &&
								!userCacheRef.current.has(doc.created_by_id)
						)
						.map((doc) => doc.created_by_id);

					if (unknownUserIds.length > 0) {
						documentsApiService
							.getDocuments({
								queryParams: {
									search_space_id: spaceId,
									page: 0,
									page_size: 20,
								},
							})
							.then((response) => {
								populateUserCache(response.items);
								if (mounted) {
									setDocuments((prev) =>
										prev.map((doc) => ({
											...doc,
											created_by_name: doc.created_by_id
												? (userCacheRef.current.get(
														doc.created_by_id
													) ?? null)
												: null,
											created_by_email: doc.created_by_id
												? (emailCacheRef.current.get(
														doc.created_by_id
													) ?? null)
												: null,
										}))
									);
								}
							})
							.catch(() => {});
					}

					setDocuments((prev) => {
						const liveIds = new Set(validItems.map((d) => d.id));
						const prevIds = new Set(prev.map((d) => d.id));

						// First callback: snapshot all Electric IDs as the baseline.
						// Everything in this set existed before the sidebar opened and
						// should only appear via API pagination, not Electric.
						if (electricBaselineIdsRef.current === null) {
							electricBaselineIdsRef.current = new Set(liveIds);
						}

						// Genuinely new = not in rendered list, not in baseline snapshot.
						// These are docs created AFTER the sidebar opened.
						const baseline = electricBaselineIdsRef.current;
						const newItems = validItems
							.filter((item) => {
								if (prevIds.has(item.id)) return false;
								if (baseline.has(item.id)) return false;
								return true;
							})
							.map(electricToDisplayDoc);

						// Track new items in baseline so they aren't re-added
						for (const item of newItems) {
							baseline.add(item.id);
						}

						// Update existing docs (status changes, title edits)
						let updated = prev.map((doc) => {
							if (liveIds.has(doc.id)) {
								const liveItem = validItems.find(
									(v) => v.id === doc.id
								);
								if (liveItem) {
									return electricToDisplayDoc(liveItem);
								}
							}
							return doc;
						});

						// Remove deleted docs (only when fully synced)
						if (isFullySynced) {
							updated = updated.filter((doc) => liveIds.has(doc.id));
						}

						if (newItems.length > 0) {
							return [...newItems, ...updated];
						}

						return updated;
					});

					// Update type counts when Electric detects changes
					if (isFullySynced && validItems.length > 0) {
						const counts: Record<string, number> = {};
						for (const item of validItems) {
							counts[item.document_type] =
								(counts[item.document_type] || 0) + 1;
						}
						setTypeCounts(counts);
						setTotal(validItems.length);
					}
				});

				liveQueryRef.current = liveQuery;
			} catch (err) {
				console.error("[useDocuments] Electric setup failed:", err);
			}
		}

		setupElectricRealtime();

		return () => {
			mounted = false;
			if (syncHandleRef.current) {
				try {
					syncHandleRef.current.unsubscribe();
				} catch {
					/* PGlite may already be closed */
				}
				syncHandleRef.current = null;
			}
			if (liveQueryRef.current) {
				try {
					liveQueryRef.current.unsubscribe?.();
				} catch {
					/* PGlite may already be closed */
				}
				liveQueryRef.current = null;
			}
		};
	}, [searchSpaceId, electricClient, electricToDisplayDoc, populateUserCache]);

	// Reset on search space change
	const prevSearchSpaceIdRef = useRef<number | null>(null);

	useEffect(() => {
		if (
			prevSearchSpaceIdRef.current !== null &&
			prevSearchSpaceIdRef.current !== searchSpaceId
		) {
			setDocuments([]);
			setTypeCounts({});
			setTotal(0);
			setHasMore(false);
			apiLoadedCountRef.current = 0;
			initialLoadDoneRef.current = false;
			electricBaselineIdsRef.current = null;
			knownApiIdsRef.current = new Set();
			userCacheRef.current.clear();
			emailCacheRef.current.clear();
		}
		prevSearchSpaceIdRef.current = searchSpaceId;
	}, [searchSpaceId]);

	// Load more pages via API
	// biome-ignore lint/correctness/useExhaustiveDependencies: typeFilterKey serializes typeFilter
	const loadMore = useCallback(async () => {
		if (loadingMore || !hasMore || !searchSpaceId) return;

		setLoadingMore(true);
		try {
			const response = await documentsApiService.getDocuments({
				queryParams: {
					search_space_id: searchSpaceId,
					skip: apiLoadedCountRef.current,
					page_size: SCROLL_PAGE_SIZE,
					...(typeFilter.length > 0 && { document_types: typeFilter }),
					sort_by: sortBy,
					sort_order: sortOrder,
				},
			});

			populateUserCache(response.items);
			const newDocs = response.items.map(apiToDisplayDoc);
			for (const doc of newDocs) {
				knownApiIdsRef.current.add(doc.id);
			}

			setDocuments((prev) => {
				const existingIds = new Set(prev.map((d) => d.id));
				const deduped = newDocs.filter((d) => !existingIds.has(d.id));
				return [...prev, ...deduped];
			});
			setTotal(response.total);
			setHasMore(response.has_more);
			apiLoadedCountRef.current += response.items.length;
		} catch (err) {
			console.error("[useDocuments] Load more failed:", err);
		} finally {
			setLoadingMore(false);
		}
	}, [
		loadingMore,
		hasMore,
		searchSpaceId,
		typeFilterKey,
		sortBy,
		sortOrder,
		populateUserCache,
		apiToDisplayDoc,
	]);

	return {
		documents,
		typeCounts,
		total,
		loading,
		loadingMore,
		hasMore,
		loadMore,
		error,
	};
}
