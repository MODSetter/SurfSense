"use client";

import { useQuery } from "@rocicorp/zero/react";
import { useCallback, useEffect, useRef, useState } from "react";
import type { DocumentSortBy, DocumentTypeEnum, SortOrder } from "@/contracts/types/document.types";
import { documentsApiService } from "@/lib/apis/documents-api.service";
import { queries } from "@/zero/queries";

export interface DocumentStatusType {
	state: "ready" | "pending" | "processing" | "failed";
	reason?: string;
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

export interface ApiDocumentInput {
	id: number;
	search_space_id: number;
	document_type: string;
	title: string;
	created_by_id?: string | null;
	created_by_name?: string | null;
	created_by_email?: string | null;
	created_at: string;
	status?: DocumentStatusType | null;
}

export function toDisplayDoc(item: ApiDocumentInput): DocumentDisplay {
	return {
		id: item.id,
		search_space_id: item.search_space_id,
		document_type: item.document_type,
		title: item.title,
		created_by_id: item.created_by_id ?? null,
		created_by_name: item.created_by_name ?? null,
		created_by_email: item.created_by_email ?? null,
		created_at: item.created_at,
		status: item.status ?? { state: "ready" },
	};
}

const EMPTY_TYPE_FILTER: DocumentTypeEnum[] = [];
const INITIAL_PAGE_SIZE = 50;
const SCROLL_PAGE_SIZE = 5;

/**
 * Paginated documents hook with Zero real-time updates.
 *
 * Architecture:
 * 1. API is the PRIMARY data source — fetches pages on demand
 * 2. Type counts come from a dedicated lightweight API endpoint
 * 3. Zero provides REAL-TIME updates (new docs, deletions, status changes)
 * 4. Server-side sorting via sort_by + sort_order params
 */
export function useDocuments(
	searchSpaceId: number | null,
	typeFilter: DocumentTypeEnum[] = EMPTY_TYPE_FILTER,
	sortBy: DocumentSortBy = "created_at",
	sortOrder: SortOrder = "desc"
) {
	const [documents, setDocuments] = useState<DocumentDisplay[]>([]);
	const [typeCounts, setTypeCounts] = useState<Record<string, number>>({});
	const [total, setTotal] = useState(0);
	const [loading, setLoading] = useState(true);
	const [loadingMore, setLoadingMore] = useState(false);
	const [hasMore, setHasMore] = useState(false);
	const [error, setError] = useState<Error | null>(null);

	const apiLoadedCountRef = useRef(0);
	const initialLoadDoneRef = useRef(false);
	const prevParamsRef = useRef<{ sortBy: string; sortOrder: string; typeFilterKey: string } | null>(
		null
	);
	const userCacheRef = useRef<Map<string, string>>(new Map());
	const emailCacheRef = useRef<Map<string, string>>(new Map());

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
		(item: ApiDocumentInput): DocumentDisplay => toDisplayDoc(item),
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
			} catch (err) {
				if (cancelled) return;
				console.error("[useDocuments] Initial load failed:", err);
				setError(err instanceof Error ? err : new Error("Failed to load documents"));
			} finally {
				if (!cancelled) setLoading(false);
			}
		};

		fetchInitialData();
		return () => {
			cancelled = true;
		};
	}, [searchSpaceId, typeFilterKey, sortBy, sortOrder, populateUserCache, apiToDisplayDoc]);

	// EFFECT 2: Zero real-time sync for document updates
	const [zeroDocuments] = useQuery(
		queries.documents.bySpace({ searchSpaceId: searchSpaceId ?? -1 })
	);

	useEffect(() => {
		if (!searchSpaceId || !zeroDocuments || !initialLoadDoneRef.current) return;

		const validItems = zeroDocuments.filter(
			(doc) => doc.id != null && doc.title != null && doc.title !== ""
		);

		const unknownUserIds = validItems.filter(
			(doc) => doc.createdById !== null && !userCacheRef.current.has(doc.createdById!)
		);

		if (unknownUserIds.length > 0) {
			documentsApiService
				.getDocuments({
					queryParams: {
						search_space_id: searchSpaceId,
						page: 0,
						page_size: 20,
					},
				})
				.then((response) => {
					populateUserCache(response.items);
					setDocuments((prev) =>
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
				})
				.catch(() => {});
		}

		const liveIds = new Set(validItems.map((d) => d.id));

		setDocuments((prev) => {
			const prevIds = new Set(prev.map((d) => d.id));

			const newItems: DocumentDisplay[] = validItems
				.filter((d) => !prevIds.has(d.id))
				.map((doc) => ({
					id: doc.id,
					search_space_id: doc.searchSpaceId,
					document_type: doc.documentType,
					title: doc.title,
					created_by_id: doc.createdById ?? null,
					created_by_name: doc.createdById
						? (userCacheRef.current.get(doc.createdById) ?? null)
						: null,
					created_by_email: doc.createdById
						? (emailCacheRef.current.get(doc.createdById) ?? null)
						: null,
					created_at: new Date(doc.createdAt).toISOString(),
					status: (doc.status as unknown as DocumentStatusType) ?? { state: "ready" },
				}));

			const liveById = new Map(validItems.map((v) => [v.id, v]));

			let updated = prev.map((existing) => {
				if (liveIds.has(existing.id)) {
					const liveItem = liveById.get(existing.id);
					if (liveItem) {
						return {
							...existing,
							title: liveItem.title,
							document_type: liveItem.documentType,
							status: (liveItem.status as unknown as DocumentStatusType) ?? {
								state: "ready" as const,
							},
						};
					}
				}
				return existing;
			});

			updated = updated.filter((doc) => liveIds.has(doc.id));

			if (newItems.length > 0) {
				return [...newItems, ...updated];
			}

			return updated;
		});

		const counts: Record<string, number> = {};
		for (const item of validItems) {
			counts[item.documentType] = (counts[item.documentType] || 0) + 1;
		}
		setTypeCounts(counts);
		setTotal(validItems.length);
	}, [searchSpaceId, zeroDocuments, populateUserCache]);

	// EFFECT 3: Reset on search space change
	const prevSearchSpaceIdRef = useRef<number | null>(null);

	useEffect(() => {
		if (prevSearchSpaceIdRef.current !== null && prevSearchSpaceIdRef.current !== searchSpaceId) {
			setDocuments([]);
			setTypeCounts({});
			setTotal(0);
			setHasMore(false);
			apiLoadedCountRef.current = 0;
			initialLoadDoneRef.current = false;
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

	const removeItems = useCallback((ids: number[]) => {
		const idSet = new Set(ids);
		setDocuments((prev) => prev.filter((item) => !idSet.has(item.id)));
		setTotal((prev) => Math.max(0, prev - ids.length));
	}, []);

	return {
		documents,
		typeCounts,
		total,
		loading,
		loadingMore,
		hasMore,
		loadMore,
		removeItems,
		error,
	};
}
