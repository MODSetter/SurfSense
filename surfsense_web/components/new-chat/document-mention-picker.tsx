"use client";

import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";
import {
	forwardRef,
	useCallback,
	useEffect,
	useImperativeHandle,
	useMemo,
	useRef,
	useState,
} from "react";
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
}

const PAGE_SIZE = 20;
const MIN_SEARCH_LENGTH = 2;
const DEBOUNCE_MS = 300;

/**
 * Debounce hook - waits until user stops typing before firing
 * Better than throttle for search: reduces request spam and prevents race conditions
 */
function useDebounced<T>(value: T, delay = DEBOUNCE_MS) {
	const [debounced, setDebounced] = useState(value);
	const timeoutRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

	useEffect(() => {
		// Clear any existing timeout
		if (timeoutRef.current) {
			clearTimeout(timeoutRef.current);
		}

		// Set new timeout - only fires after user stops typing for `delay` ms
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
	{ searchSpaceId, onSelectionChange, onDone, initialSelectedDocuments = [], externalSearch = "" },
	ref
) {
	const queryClient = useQueryClient();

	// Use external search with debounce - waits until user stops typing
	// Reduces request spam and prevents race conditions with stale results
	const search = externalSearch;
	const debouncedSearch = useDebounced(search, DEBOUNCE_MS);
	const [highlightedIndex, setHighlightedIndex] = useState(0);
	const itemRefs = useRef<Map<number, HTMLButtonElement>>(new Map());
	const scrollContainerRef = useRef<HTMLDivElement>(null);
	const shouldScrollRef = useRef(false); // Track if scroll should happen (only for keyboard navigation)

	// State for pagination
	const [accumulatedDocuments, setAccumulatedDocuments] = useState<
		Pick<Document, "id" | "title" | "document_type">[]
	>([]);
	const [currentPage, setCurrentPage] = useState(0);
	const [hasMore, setHasMore] = useState(false);
	const [isLoadingMore, setIsLoadingMore] = useState(false);

	// Check if search is long enough
	const isSearchValid = debouncedSearch.trim().length >= MIN_SEARCH_LENGTH;
	const shouldSearch = debouncedSearch.trim().length > 0;

	// Prefetch first page when picker mounts - results appear instantly
	useEffect(() => {
		if (!searchSpaceId) return;

		const prefetchParams = {
			search_space_id: searchSpaceId,
			page: 0,
			page_size: PAGE_SIZE,
		};

		// Prefetch document titles (user docs)
		queryClient.prefetchQuery({
			queryKey: ["document-titles", prefetchParams],
			queryFn: () => documentsApiService.searchDocumentTitles({ queryParams: prefetchParams }),
			staleTime: 60 * 1000,
		});

		// Prefetch SurfSense docs
		queryClient.prefetchQuery({
			queryKey: ["surfsense-docs-mention", "", false],
			queryFn: () =>
				documentsApiService.getSurfsenseDocs({
					queryParams: { page: 0, page_size: PAGE_SIZE },
				}),
			staleTime: 3 * 60 * 1000,
		});
	}, [searchSpaceId, queryClient]);

	// Reset pagination when search or search space changes
	// Don't clear accumulatedDocuments - let new data replace it smoothly (prevents "No documents found" flash)
	// biome-ignore lint/correctness/useExhaustiveDependencies: intentionally reset pagination when search/space changes
	useEffect(() => {
		// Keep previous documents visible while new query is fetching (smooth UX)
		// setAccumulatedDocuments([]); // Removed to prevent flash of "No documents found"
		setCurrentPage(0);
		setHasMore(false);
		setHighlightedIndex(0);
	}, [debouncedSearch, searchSpaceId]);

	// Query params for lightweight title search
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

	// Use the new lightweight endpoint for document title search
	// TanStack Query provides signal for automatic request cancellation
	// keepPreviousData: shows old results while fetching new ones (no spinner flicker)
	const {
		data: titleSearchResults,
		isLoading: isTitleSearchLoading,
		isFetching: isTitleSearchFetching,
	} = useQuery({
		queryKey: ["document-titles", titleSearchParams],
		queryFn: ({ signal }) =>
			documentsApiService.searchDocumentTitles({ queryParams: titleSearchParams }, signal),
		staleTime: 60 * 1000, // 1 minute - shorter for fresher results
		enabled: !!searchSpaceId && currentPage === 0 && (!shouldSearch || isSearchValid),
		placeholderData: keepPreviousData,
	});

	// Use query for fetching first page of SurfSense docs
	// TanStack Query provides signal for automatic request cancellation
	// keepPreviousData: shows old results while fetching new ones (no spinner flicker)
	const {
		data: surfsenseDocs,
		isLoading: isSurfsenseDocsLoading,
		isFetching: isSurfsenseDocsFetching,
	} = useQuery({
		queryKey: ["surfsense-docs-mention", debouncedSearch, isSearchValid],
		queryFn: ({ signal }) =>
			documentsApiService.getSurfsenseDocs({ queryParams: surfsenseDocsQueryParams }, signal),
		staleTime: 3 * 60 * 1000,
		enabled: !shouldSearch || isSearchValid,
		placeholderData: keepPreviousData,
	});

	// Client-side filter to verify search term is actually in the title (handles backend fuzzy false positives)
	const filterBySearchTerm = useCallback(
		(docs: Pick<Document, "id" | "title" | "document_type">[]) => {
			if (!isSearchValid) return docs; // No filtering when not searching
			const searchLower = debouncedSearch.trim().toLowerCase();
			return docs.filter((doc) => doc.title.toLowerCase().includes(searchLower));
		},
		[debouncedSearch, isSearchValid]
	);

	// Update accumulated documents when first page loads - combine both sources
	useEffect(() => {
		if (currentPage === 0) {
			const combinedDocs: Pick<Document, "id" | "title" | "document_type">[] = [];

			// Add SurfSense docs first (they appear at top)
			if (surfsenseDocs?.items) {
				for (const doc of surfsenseDocs.items) {
					combinedDocs.push({
						id: doc.id,
						title: doc.title,
						document_type: "SURFSENSE_DOCS",
					});
				}
			}

			// Add regular documents from lightweight endpoint
			if (titleSearchResults?.items) {
				combinedDocs.push(...titleSearchResults.items);
				setHasMore(titleSearchResults.has_more);
			}

			// Apply client-side filter to remove fuzzy false positives
			setAccumulatedDocuments(filterBySearchTerm(combinedDocs));
		}
	}, [titleSearchResults, surfsenseDocs, currentPage, filterBySearchTerm]);

	// Function to load next page using lightweight endpoint
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

	// Infinite scroll handler
	const handleScroll = useCallback(
		(e: React.UIEvent<HTMLDivElement>) => {
			const target = e.currentTarget;
			const scrollBottom = target.scrollHeight - target.scrollTop - target.clientHeight;

			// Load more when within 50px of bottom
			if (scrollBottom < 50 && hasMore && !isLoadingMore) {
				loadNextPage();
			}
		},
		[hasMore, isLoadingMore, loadNextPage]
	);

	const actualDocuments = accumulatedDocuments;
	const actualLoading = (isTitleSearchLoading || isSurfsenseDocsLoading) && currentPage === 0;
	const isFetchingResults = isTitleSearchFetching || isSurfsenseDocsFetching;

	// Show hint when search is too short
	const showSearchHint = shouldSearch && !isSearchValid;

	// Hide popup when user is searching and no documents match (only after fetch completes)
	// We return null instead of calling onDone() so that mention mode stays active
	// This allows the popup to reappear when user deletes characters and results come back
	const hasNoSearchResults =
		isSearchValid && !actualLoading && !isFetchingResults && actualDocuments.length === 0;

	// Split documents into SurfSense docs and user docs for grouped rendering
	const surfsenseDocsList = useMemo(
		() => actualDocuments.filter((doc) => doc.document_type === "SURFSENSE_DOCS"),
		[actualDocuments]
	);
	const userDocsList = useMemo(
		() => actualDocuments.filter((doc) => doc.document_type !== "SURFSENSE_DOCS"),
		[actualDocuments]
	);

	// Track already selected documents using unique key (document_type:id) to avoid ID collisions
	const selectedKeys = useMemo(
		() => new Set(initialSelectedDocuments.map((d) => `${d.document_type}:${d.id}`)),
		[initialSelectedDocuments]
	);

	// Filter out already selected documents for navigation
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

	// Scroll highlighted item into view - only for keyboard navigation, not mouse hover
	useEffect(() => {
		// Only scroll if this was triggered by keyboard navigation
		if (!shouldScrollRef.current) {
			return;
		}

		// Reset the flag after checking
		shouldScrollRef.current = false;

		// Use requestAnimationFrame to ensure DOM is updated
		const rafId = requestAnimationFrame(() => {
			const item = itemRefs.current.get(highlightedIndex);
			const container = scrollContainerRef.current;

			if (item && container) {
				// Get item and container positions
				const itemRect = item.getBoundingClientRect();
				const containerRect = container.getBoundingClientRect();

				// Calculate if item is outside viewport (with some padding)
				const padding = 8; // Small padding to ensure item is fully visible
				const isAboveViewport = itemRect.top < containerRect.top + padding;
				const isBelowViewport = itemRect.bottom > containerRect.bottom - padding;

				if (isAboveViewport || isBelowViewport) {
					// Calculate scroll position to center the item in viewport
					const itemOffsetTop = item.offsetTop;
					const containerHeight = container.clientHeight;
					const itemHeight = item.offsetHeight;

					// Center the item in the viewport
					const targetScrollTop = itemOffsetTop - containerHeight / 2 + itemHeight / 2;

					// Ensure we don't scroll beyond bounds
					const maxScrollTop = container.scrollHeight - containerHeight;
					const clampedScrollTop = Math.max(0, Math.min(targetScrollTop, maxScrollTop));

					// Smooth scroll to target position
					container.scrollTo({
						top: clampedScrollTop,
						behavior: "smooth",
					});
				}
			}
		});

		return () => cancelAnimationFrame(rafId);
	}, [highlightedIndex]);

	// Reset highlighted index when external search changes
	const prevSearchRef = useRef(search);
	if (prevSearchRef.current !== search) {
		prevSearchRef.current = search;
		if (highlightedIndex !== 0) {
			setHighlightedIndex(0);
		}
	}

	// Expose methods to parent via ref
	useImperativeHandle(
		ref,
		() => ({
			selectHighlighted: () => {
				if (selectableDocuments[highlightedIndex]) {
					handleSelectDocument(selectableDocuments[highlightedIndex]);
				}
			},
			moveUp: () => {
				shouldScrollRef.current = true; // Enable scrolling for keyboard navigation
				setHighlightedIndex((prev) => (prev > 0 ? prev - 1 : selectableDocuments.length - 1));
			},
			moveDown: () => {
				shouldScrollRef.current = true; // Enable scrolling for keyboard navigation
				setHighlightedIndex((prev) => (prev < selectableDocuments.length - 1 ? prev + 1 : 0));
			},
		}),
		[selectableDocuments, highlightedIndex, handleSelectDocument]
	);

	// Handle keyboard navigation
	const handleKeyDown = useCallback(
		(e: React.KeyboardEvent) => {
			if (selectableDocuments.length === 0) return;

			switch (e.key) {
				case "ArrowDown":
					e.preventDefault();
					shouldScrollRef.current = true; // Enable scrolling for keyboard navigation
					setHighlightedIndex((prev) => (prev < selectableDocuments.length - 1 ? prev + 1 : 0));
					break;
				case "ArrowUp":
					e.preventDefault();
					shouldScrollRef.current = true; // Enable scrolling for keyboard navigation
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

	// Hide popup visually when searching returns no results
	// Don't call onDone() - this keeps mention mode active so popup reappears when results come back
	if (hasNoSearchResults) {
		return null;
	}

	return (
		<div
			className="flex flex-col w-[280px] sm:w-[320px] bg-popover rounded-lg"
			onKeyDown={handleKeyDown}
			role="listbox"
			tabIndex={-1}
		>
			{/* Document List - Shows max 5 items on mobile, 7-8 items on desktop */}
			<div
				ref={scrollContainerRef}
				className="max-h-[180px] sm:max-h-[280px] overflow-y-auto"
				onScroll={handleScroll}
			>
				{showSearchHint ? (
					<div className="flex flex-col items-center justify-center py-4 text-center px-4">
						<p className="text-sm text-muted-foreground">
							Type {MIN_SEARCH_LENGTH - debouncedSearch.trim().length} more character
							{MIN_SEARCH_LENGTH - debouncedSearch.trim().length > 1 ? "s" : ""} to search
						</p>
					</div>
				) : actualLoading ? (
					<div className="flex items-center justify-center py-4">
						<div className="animate-spin h-5 w-5 border-2 border-primary border-t-transparent rounded-full" />
					</div>
				) : actualDocuments.length > 0 ? (
					<div className="py-1 px-2">
						{/* SurfSense Documentation Section */}
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

						{/* User Documents Section */}
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

						{/* Loading indicator for additional pages */}
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
