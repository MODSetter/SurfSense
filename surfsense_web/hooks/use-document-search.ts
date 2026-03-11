"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { DocumentTypeEnum } from "@/contracts/types/document.types";
import { documentsApiService } from "@/lib/apis/documents-api.service";
import { type DocumentDisplay, toDisplayDoc } from "./use-documents";

const SEARCH_INITIAL_SIZE = 20;
const SEARCH_SCROLL_SIZE = 5;

/**
 * Paginated document search hook.
 *
 * Handles title-based search with server-side filtering,
 * pagination via skip/page_size, and staleness detection
 * so fast typing never renders stale results.
 *
 * @param searchSpaceId - The search space to search within
 * @param query - The debounced search query
 * @param activeTypes - Document types to filter by
 * @param enabled - When false the hook resets and stops fetching
 */
export function useDocumentSearch(
	searchSpaceId: number,
	query: string,
	activeTypes: DocumentTypeEnum[],
	enabled: boolean
) {
	const [documents, setDocuments] = useState<DocumentDisplay[]>([]);
	const [loading, setLoading] = useState(false);
	const [loadingMore, setLoadingMore] = useState(false);
	const [hasMore, setHasMore] = useState(false);
	const [error, setError] = useState(false);

	const apiLoadedRef = useRef(0);
	const queryRef = useRef(query);

	const isActive = enabled && !!query.trim();
	const activeTypesKey = activeTypes.join(",");

	// biome-ignore lint/correctness/useExhaustiveDependencies: activeTypesKey serializes activeTypes
	useEffect(() => {
		if (!isActive || !searchSpaceId) {
			setDocuments([]);
			setHasMore(false);
			setError(false);
			apiLoadedRef.current = 0;
			return;
		}

		let cancelled = false;
		queryRef.current = query;
		setLoading(true);
		setError(false);

		documentsApiService
			.searchDocuments({
				queryParams: {
					search_space_id: searchSpaceId,
					page: 0,
					page_size: SEARCH_INITIAL_SIZE,
					title: query.trim(),
					...(activeTypes.length > 0 && { document_types: activeTypes }),
				},
			})
			.then((response) => {
				if (cancelled || queryRef.current !== query) return;
				setDocuments(response.items.map(toDisplayDoc));
				setHasMore(response.has_more);
				apiLoadedRef.current = response.items.length;
			})
			.catch((err) => {
				if (cancelled) return;
				console.error("[useDocumentSearch] Search failed:", err);
				setError(true);
			})
			.finally(() => {
				if (!cancelled) setLoading(false);
			});

		return () => {
			cancelled = true;
		};
	}, [query, searchSpaceId, isActive, activeTypesKey]);

	// biome-ignore lint/correctness/useExhaustiveDependencies: activeTypesKey serializes activeTypes
	const loadMore = useCallback(async () => {
		if (loadingMore || !isActive || !hasMore) return;

		setLoadingMore(true);
		try {
			const response = await documentsApiService.searchDocuments({
				queryParams: {
					search_space_id: searchSpaceId,
					skip: apiLoadedRef.current,
					page_size: SEARCH_SCROLL_SIZE,
					title: query.trim(),
					...(activeTypes.length > 0 && { document_types: activeTypes }),
				},
			});
			if (queryRef.current !== query) return;

			setDocuments((prev) => [...prev, ...response.items.map(toDisplayDoc)]);
			setHasMore(response.has_more);
			apiLoadedRef.current += response.items.length;
		} catch (err) {
			console.error("[useDocumentSearch] Load more failed:", err);
		} finally {
			setLoadingMore(false);
		}
	}, [loadingMore, isActive, hasMore, searchSpaceId, query, activeTypesKey]);

	const removeItems = useCallback((ids: number[]) => {
		const idSet = new Set(ids);
		setDocuments((prev) => prev.filter((item) => !idSet.has(item.id)));
	}, []);

	return {
		documents,
		loading,
		loadingMore,
		hasMore,
		loadMore,
		error,
		removeItems,
	};
}
