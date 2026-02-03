"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
	forwardRef,
	useCallback,
	useEffect,
	useImperativeHandle,
	useMemo,
	useRef,
	useState,
} from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";
import type { Document, SearchDocumentTitlesResponse } from "@/contracts/types/document.types";
import { documentsApiService } from "@/lib/apis/documents-api.service";
import { cn } from "@/lib/utils";

export interface DocumentMentionPickerRef {
	selectHighlighted: () => void;
	moveUp: () => void;
	moveDown: () => void;
}

interface DocumentMentionPickerProps {
	searchSpaceId: number;
	onSelectionChange: (documents: Pick<Document, "id" | "title" | "document_type">[]) => void;
	onDone: () => void;
	initialSelectedDocuments?: Pick<Document, "id" | "title" | "document_type">[];
	externalSearch?: string;
	/** Positioning styles for the container */
	containerStyle?: React.CSSProperties;
}

const PAGE_SIZE = 20;
const MIN_SEARCH_LENGTH = 2;
const DEBOUNCE_MS = 100;

/**
 * Custom debounce hook that delays value updates until user input stabilizes.
 * Preferred over throttling for search inputs as it reduces API request frequency
 * and prevents race conditions from stale responses overtaking recent ones.
 */
function useDebounced<T>(value: T, delay = DEBOUNCE_MS) {
	const [debounced, setDebounced] = useState(value);
	const timeoutRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

	useEffect(() => {
		if (timeoutRef.current) {
			clearTimeout(timeoutRef.current);
		}

		timeoutRef.current = setTimeout(() => {
			setDebounced(value);
		}, delay);

		return () => {
			if (timeoutRef.current) {
				clearTimeout(timeoutRef.current);
			}
		};
	}, [value, delay]);

	return debounced;
}

export const DocumentMentionPicker = forwardRef<
	DocumentMentionPickerRef,
	DocumentMentionPickerProps
>(function DocumentMentionPicker(
	{
		searchSpaceId,
		onSelectionChange,
		onDone,
		initialSelectedDocuments = [],
		externalSearch = "",
		containerStyle,
	},
	ref
) {
	// Debounced search value to minimize API calls and prevent race conditions
	const search = externalSearch;
	const debouncedSearch = useDebounced(search, DEBOUNCE_MS);
	const [highlightedIndex, setHighlightedIndex] = useState(0);
	const itemRefs = useRef<Map<number, HTMLButtonElement>>(new Map());
	const scrollContainerRef = useRef<HTMLDivElement>(null);
	const shouldScrollRef = useRef(false); // Keyboard navigation scroll flag

	// Pagination state for infinite scroll
	const [accumulatedDocuments, setAccumulatedDocuments] = useState<
		Pick<Document, "id" | "title" | "document_type">[]
	>([]);
	const [currentPage, setCurrentPage] = useState(0);
	const [hasMore, setHasMore] = useState(false);
	const [isLoadingMore, setIsLoadingMore] = useState(false);

	/**
	 * Search Strategy:
	 * - Single character (length === 1): Client-side filtering for instant results
	 * - Two or more characters (length >= 2): Server-side search with pg_trgm index
	 * This hybrid approach optimizes UX by providing immediate feedback for short queries
	 * while leveraging efficient database indexing for longer, more specific searches.
	 */
	const isSearchValid = debouncedSearch.trim().length >= MIN_SEARCH_LENGTH;
	const shouldSearch = debouncedSearch.trim().length > 0;
	const isSingleCharSearch = debouncedSearch.trim().length === 1;

	// Reset pagination state when search query or search space changes.
	// Documents are not cleared to maintain visual continuity during fetches.
	// biome-ignore lint/correctness/useExhaustiveDependencies: Intentional reset on search/space change
	useEffect(() => {
		setCurrentPage(0);
		setHasMore(false);
		setHighlightedIndex(0);
	}, [debouncedSearch, searchSpaceId]);

	// Query parameters for lightweight title search endpoint
	const titleSearchParams = useMemo(
		() => ({
			search_space_id: searchSpaceId,
			page: 0,
			page_size: PAGE_SIZE,
			...(isSearchValid ? { title: debouncedSearch.trim() } : {}),
		}),
		[searchSpaceId, debouncedSearch, isSearchValid]
	);

	const surfsenseDocsQueryParams = useMemo(() => {
		const params: { page: number; page_size: number; title?: string } = {
			page: 0,
			page_size: PAGE_SIZE,
		};
		if (isSearchValid) {
			params.title = debouncedSearch.trim();
		}
		return params;
	}, [debouncedSearch, isSearchValid]);

	/**
	 * TanStack Query for document title search.
	 * - Uses AbortSignal for automatic request cancellation on query key changes
	 * - placeholderData: keepPreviousData maintains UI stability during fetches
	 * - Only triggers server-side search when isSearchValid (2+ characters)
	 */
	const { data: titleSearchResults, isLoading: isTitleSearchLoading } = useQuery({
		queryKey: ["document-titles", titleSearchParams],
		queryFn: ({ signal }) =>
			documentsApiService.searchDocumentTitles({ queryParams: titleSearchParams }, signal),
		staleTime: 60 * 1000,
		enabled: !!searchSpaceId && currentPage === 0 && (!shouldSearch || isSearchValid),
		placeholderData: keepPreviousData,
	});

	/**
	 * TanStack Query for SurfSense documentation.
	 * - Uses AbortSignal for automatic request cancellation
	 * - placeholderData: keepPreviousData prevents UI flicker during refetches
	 */
	const { data: surfsenseDocs, isLoading: isSurfsenseDocsLoading } = useQuery({
		queryKey: ["surfsense-docs-mention", debouncedSearch, isSearchValid],
		queryFn: ({ signal }) =>
			documentsApiService.getSurfsenseDocs({ queryParams: surfsenseDocsQueryParams }, signal),
		staleTime: 3 * 60 * 1000,
		enabled: !shouldSearch || isSearchValid,
		placeholderData: keepPreviousData,
	});

	// Post-fetch filter to eliminate false positives from backend fuzzy matching
	const filterBySearchTerm = useCallback(
		(docs: Pick<Document, "id" | "title" | "document_type">[]) => {
			if (!isSearchValid) return docs; // No filtering when not searching
			const searchLower = debouncedSearch.trim().toLowerCase();
			return docs.filter((doc) => doc.title.toLowerCase().includes(searchLower));
		},
		[debouncedSearch, isSearchValid]
	);

	// Combine and update document list when first page data arrives
	useEffect(() => {
		if (currentPage === 0) {
			const combinedDocs: Pick<Document, "id" | "title" | "document_type">[] = [];

			// SurfSense docs displayed first in the list
			if (surfsenseDocs?.items) {
				for (const doc of surfsenseDocs.items) {
					combinedDocs.push({
						id: doc.id,
						title: doc.title,
						document_type: "SURFSENSE_DOCS",
					});
				}
			}

			if (titleSearchResults?.items) {
				combinedDocs.push(...titleSearchResults.items);
				setHasMore(titleSearchResults.has_more);
			}

			setAccumulatedDocuments(filterBySearchTerm(combinedDocs));
		}
	}, [titleSearchResults, surfsenseDocs, currentPage, filterBySearchTerm]);

	// Load next page for infinite scroll pagination
	const loadNextPage = useCallback(async () => {
		if (isLoadingMore || !hasMore) return;

		const nextPage = currentPage + 1;
		setIsLoadingMore(true);

		try {
			const queryParams = {
				search_space_id: searchSpaceId,
				page: nextPage,
				page_size: PAGE_SIZE,
				...(isSearchValid ? { title: debouncedSearch.trim() } : {}),
			};
			const response: SearchDocumentTitlesResponse = await documentsApiService.searchDocumentTitles(
				{ queryParams }
			);

			setAccumulatedDocuments((prev) => [...prev, ...response.items]);
			setHasMore(response.has_more);
			setCurrentPage(nextPage);
		} catch (error) {
			console.error("Failed to load next page:", error);
		} finally {
			setIsLoadingMore(false);
		}
	}, [currentPage, hasMore, isLoadingMore, debouncedSearch, searchSpaceId, isSearchValid]);

	// Trigger pagination when user scrolls near the bottom (50px threshold)
	const handleScroll = useCallback(
		(e: React.UIEvent<HTMLDivElement>) => {
			const target = e.currentTarget;
			const scrollBottom = target.scrollHeight - target.scrollTop - target.clientHeight;

			if (scrollBottom < 50 && hasMore && !isLoadingMore) {
				loadNextPage();
			}
		},
		[hasMore, isLoadingMore, loadNextPage]
	);

	/**
	 * Client-side filtering for single character searches.
	 * Filters cached documents locally for instant feedback without additional API calls.
	 * Server-side search is reserved for 2+ character queries to leverage database indexing.
	 */
	const clientFilteredDocs = useMemo(() => {
		if (!isSingleCharSearch) return null;
		const searchLower = debouncedSearch.trim().toLowerCase();
		return accumulatedDocuments.filter((doc) => doc.title.toLowerCase().includes(searchLower));
	}, [isSingleCharSearch, debouncedSearch, accumulatedDocuments]);

	// Select data source based on search length: client-filtered for single char, server results for 2+
	const actualDocuments = isSingleCharSearch ? (clientFilteredDocs ?? []) : accumulatedDocuments;
	// Only show loading spinner on initial load (no documents yet), not during subsequent searches
	const actualLoading =
		(isTitleSearchLoading || isSurfsenseDocsLoading) &&
		currentPage === 0 &&
		!isSingleCharSearch &&
		accumulatedDocuments.length === 0;
	// Partition documents by type for grouped UI rendering
	const surfsenseDocsList = useMemo(
		() => actualDocuments.filter((doc) => doc.document_type === "SURFSENSE_DOCS"),
		[actualDocuments]
	);
	const userDocsList = useMemo(
		() => actualDocuments.filter((doc) => doc.document_type !== "SURFSENSE_DOCS"),
		[actualDocuments]
	);

	// Track selected documents with composite key (document_type:id) to prevent cross-type ID collisions
	const selectedKeys = useMemo(
		() => new Set(initialSelectedDocuments.map((d) => `${d.document_type}:${d.id}`)),
		[initialSelectedDocuments]
	);

	// Exclude already-selected documents from keyboard navigation
	const selectableDocuments = useMemo(
		() => actualDocuments.filter((doc) => !selectedKeys.has(`${doc.document_type}:${doc.id}`)),
		[actualDocuments, selectedKeys]
	);

	const handleSelectDocument = useCallback(
		(doc: Pick<Document, "id" | "title" | "document_type">) => {
			onSelectionChange([...initialSelectedDocuments, doc]);
			onDone();
		},
		[initialSelectedDocuments, onSelectionChange, onDone]
	);

	// Auto-scroll highlighted item into view (keyboard navigation only, not mouse hover)
	useEffect(() => {
		if (!shouldScrollRef.current) {
			return;
		}
		shouldScrollRef.current = false;

		const rafId = requestAnimationFrame(() => {
			const item = itemRefs.current.get(highlightedIndex);
			const container = scrollContainerRef.current;

			if (item && container) {
				const itemRect = item.getBoundingClientRect();
				const containerRect = container.getBoundingClientRect();
				const padding = 8;
				const isAboveViewport = itemRect.top < containerRect.top + padding;
				const isBelowViewport = itemRect.bottom > containerRect.bottom - padding;

				if (isAboveViewport || isBelowViewport) {
					const itemOffsetTop = item.offsetTop;
					const containerHeight = container.clientHeight;
					const itemHeight = item.offsetHeight;
					const targetScrollTop = itemOffsetTop - containerHeight / 2 + itemHeight / 2;
					const maxScrollTop = container.scrollHeight - containerHeight;
					const clampedScrollTop = Math.max(0, Math.min(targetScrollTop, maxScrollTop));

					container.scrollTo({
						top: clampedScrollTop,
						behavior: "smooth",
					});
				}
			}
		});

		return () => cancelAnimationFrame(rafId);
	}, [highlightedIndex]);

	// Reset highlight position when search query changes
	const prevSearchRef = useRef(search);
	if (prevSearchRef.current !== search) {
		prevSearchRef.current = search;
		if (highlightedIndex !== 0) {
			setHighlightedIndex(0);
		}
	}

	// Expose navigation and selection methods to parent component via ref
	useImperativeHandle(
		ref,
		() => ({
			selectHighlighted: () => {
				if (selectableDocuments[highlightedIndex]) {
					handleSelectDocument(selectableDocuments[highlightedIndex]);
				}
			},
			moveUp: () => {
				shouldScrollRef.current = true;
				setHighlightedIndex((prev) => (prev > 0 ? prev - 1 : selectableDocuments.length - 1));
			},
			moveDown: () => {
				shouldScrollRef.current = true;
				setHighlightedIndex((prev) => (prev < selectableDocuments.length - 1 ? prev + 1 : 0));
			},
		}),
		[selectableDocuments, highlightedIndex, handleSelectDocument]
	);

	// Keyboard navigation handler for arrow keys, Enter, and Escape
	const handleKeyDown = useCallback(
		(e: React.KeyboardEvent) => {
			if (selectableDocuments.length === 0) return;

			switch (e.key) {
				case "ArrowDown":
					e.preventDefault();
					shouldScrollRef.current = true;
					setHighlightedIndex((prev) => (prev < selectableDocuments.length - 1 ? prev + 1 : 0));
					break;
				case "ArrowUp":
					e.preventDefault();
					shouldScrollRef.current = true;
					setHighlightedIndex((prev) => (prev > 0 ? prev - 1 : selectableDocuments.length - 1));
					break;
				case "Enter":
					e.preventDefault();
					if (selectableDocuments[highlightedIndex]) {
						handleSelectDocument(selectableDocuments[highlightedIndex]);
					}
					break;
				case "Escape":
					e.preventDefault();
					onDone();
					break;
			}
		},
		[selectableDocuments, highlightedIndex, handleSelectDocument, onDone]
	);

	// Hide popup when there are no documents to display (regardless of fetch state)
	// Search continues in background; popup reappears when results arrive
	if (!actualLoading && actualDocuments.length === 0) {
		return null;
	}

	return (
		<div
			className="fixed shadow-2xl rounded-lg border border-border overflow-hidden bg-popover flex flex-col w-[280px] sm:w-[320px]"
			style={{
				zIndex: 9999,
				...containerStyle,
			}}
			onKeyDown={handleKeyDown}
			role="listbox"
			tabIndex={-1}
		>
			{/* Scrollable document list with responsive height */}
			<div
				ref={scrollContainerRef}
				className="max-h-[180px] sm:max-h-[280px] overflow-y-auto"
				onScroll={handleScroll}
			>
				{actualLoading ? (
					<div className="py-1 px-2">
						<div className="px-3 py-2">
							<Skeleton className="h-[16px] w-24" />
						</div>
						{["a", "b", "c", "d", "e"].map((id, i) => (
							<div
								key={id}
								className={cn(
									"w-full flex items-center gap-2 px-3 py-2 text-left rounded-md",
									i >= 3 && "hidden sm:flex"
								)}
							>
								<span className="shrink-0">
									<Skeleton className="h-4 w-4" />
								</span>
								<span className="flex-1 text-sm">
									<Skeleton className="h-[20px]" style={{ width: `${60 + ((i * 7) % 30)}%` }} />
								</span>
							</div>
						))}
					</div>
				) : actualDocuments.length > 0 ? (
					<div className="py-1 px-2">
						{/* SurfSense Documentation */}
						{surfsenseDocsList.length > 0 && (
							<>
								<div className="px-3 py-2 text-xs font-bold text-muted-foreground/55">
									SurfSense Docs
								</div>
								{surfsenseDocsList.map((doc) => {
									const docKey = `${doc.document_type}:${doc.id}`;
									const isAlreadySelected = selectedKeys.has(docKey);
									const selectableIndex = selectableDocuments.findIndex(
										(d) => d.document_type === doc.document_type && d.id === doc.id
									);
									const isHighlighted = !isAlreadySelected && selectableIndex === highlightedIndex;

									return (
										<button
											key={docKey}
											ref={(el) => {
												if (el && selectableIndex >= 0) {
													itemRefs.current.set(selectableIndex, el);
												}
											}}
											type="button"
											onClick={() => !isAlreadySelected && handleSelectDocument(doc)}
											onMouseEnter={() => {
												if (!isAlreadySelected && selectableIndex >= 0) {
													setHighlightedIndex(selectableIndex);
												}
											}}
											disabled={isAlreadySelected}
											className={cn(
												"w-full flex items-center gap-2 px-3 py-2 text-left transition-colors rounded-md",
												isAlreadySelected ? "opacity-50 cursor-not-allowed" : "cursor-pointer",
												isHighlighted && "bg-accent"
											)}
										>
											<span className="shrink-0 text-muted-foreground text-sm">
												{getConnectorIcon(doc.document_type)}
											</span>
											<span className="flex-1 text-sm truncate" title={doc.title}>
												{doc.title}
											</span>
										</button>
									);
								})}
							</>
						)}

						{/* User Documents */}
						{userDocsList.length > 0 && (
							<>
								<div className="px-3 py-2 text-xs font-bold text-muted-foreground/55">
									Your Documents
								</div>
								{userDocsList.map((doc) => {
									const docKey = `${doc.document_type}:${doc.id}`;
									const isAlreadySelected = selectedKeys.has(docKey);
									const selectableIndex = selectableDocuments.findIndex(
										(d) => d.document_type === doc.document_type && d.id === doc.id
									);
									const isHighlighted = !isAlreadySelected && selectableIndex === highlightedIndex;

									return (
										<button
											key={docKey}
											ref={(el) => {
												if (el && selectableIndex >= 0) {
													itemRefs.current.set(selectableIndex, el);
												}
											}}
											type="button"
											onClick={() => !isAlreadySelected && handleSelectDocument(doc)}
											onMouseEnter={() => {
												if (!isAlreadySelected && selectableIndex >= 0) {
													setHighlightedIndex(selectableIndex);
												}
											}}
											disabled={isAlreadySelected}
											className={cn(
												"w-full flex items-center gap-2 px-3 py-2 text-left transition-colors rounded-md",
												isAlreadySelected ? "opacity-50 cursor-not-allowed" : "cursor-pointer",
												isHighlighted && "bg-accent"
											)}
										>
											<span className="shrink-0 text-muted-foreground text-sm">
												{getConnectorIcon(doc.document_type)}
											</span>
											<span className="flex-1 text-sm truncate" title={doc.title}>
												{doc.title}
											</span>
										</button>
									);
								})}
							</>
						)}

						{/* Pagination loading indicator */}
						{isLoadingMore && (
							<div className="flex items-center justify-center py-2">
								<div className="animate-spin h-4 w-4 border-2 border-primary border-t-transparent rounded-full" />
							</div>
						)}
					</div>
				) : null}
			</div>
		</div>
	);
});
