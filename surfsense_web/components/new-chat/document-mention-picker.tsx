"use client";

import { useQuery } from "@tanstack/react-query";
import { FileText } from "lucide-react";
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
import type { Document, GetDocumentsResponse } from "@/contracts/types/document.types";
import { documentsApiService } from "@/lib/apis/documents-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";
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

function useDebounced<T>(value: T, delay = 300) {
	const [debounced, setDebounced] = useState(value);
	useEffect(() => {
		const t = setTimeout(() => setDebounced(value), delay);
		return () => clearTimeout(t);
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
	// Use external search
	const search = externalSearch;
	const debouncedSearch = useDebounced(search, 150);
	const [highlightedIndex, setHighlightedIndex] = useState(0);
	const itemRefs = useRef<Map<number, HTMLButtonElement>>(new Map());
	const scrollContainerRef = useRef<HTMLDivElement>(null);

	// State for pagination
	const [accumulatedDocuments, setAccumulatedDocuments] = useState<
		Pick<Document, "id" | "title" | "document_type">[]
	>([]);
	const [currentPage, setCurrentPage] = useState(0);
	const [hasMore, setHasMore] = useState(false);
	const [isLoadingMore, setIsLoadingMore] = useState(false);

	// Reset pagination when search or search space changes
	// biome-ignore lint/correctness/useExhaustiveDependencies: intentionally reset pagination when search/space changes
	useEffect(() => {
		setAccumulatedDocuments([]);
		setCurrentPage(0);
		setHasMore(false);
		setHighlightedIndex(0);
	}, [debouncedSearch, searchSpaceId]);

	// Query params for initial fetch (page 0)
	const fetchQueryParams = useMemo(
		() => ({
			search_space_id: searchSpaceId,
			page: 0,
			page_size: PAGE_SIZE,
		}),
		[searchSpaceId]
	);

	const searchQueryParams = useMemo(() => {
		return {
			search_space_id: searchSpaceId,
			page: 0,
			page_size: PAGE_SIZE,
			title: debouncedSearch,
		};
	}, [debouncedSearch, searchSpaceId]);

	const surfsenseDocsQueryParams = useMemo(() => {
		const params: { page: number; page_size: number; title?: string } = {
			page: 0,
			page_size: PAGE_SIZE,
		};
		if (debouncedSearch.trim()) {
			params.title = debouncedSearch;
		}
		return params;
	}, [debouncedSearch]);

	// Use query for fetching first page of documents
	const { data: documents, isLoading: isDocumentsLoading } = useQuery({
		queryKey: cacheKeys.documents.withQueryParams(fetchQueryParams),
		queryFn: () => documentsApiService.getDocuments({ queryParams: fetchQueryParams }),
		staleTime: 3 * 60 * 1000,
		enabled: !!searchSpaceId && !debouncedSearch.trim() && currentPage === 0,
	});

	// Searching - first page
	const { data: searchedDocuments, isLoading: isSearchedDocumentsLoading } = useQuery({
		queryKey: cacheKeys.documents.withQueryParams(searchQueryParams),
		queryFn: () => documentsApiService.searchDocuments({ queryParams: searchQueryParams }),
		staleTime: 3 * 60 * 1000,
		enabled: !!searchSpaceId && !!debouncedSearch.trim() && currentPage === 0,
	});

	// Use query for fetching first page of SurfSense docs
	const { data: surfsenseDocs, isLoading: isSurfsenseDocsLoading } = useQuery({
		queryKey: ["surfsense-docs-mention", debouncedSearch],
		queryFn: () => documentsApiService.getSurfsenseDocs({ queryParams: surfsenseDocsQueryParams }),
		staleTime: 3 * 60 * 1000,
	});

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

			// Add regular documents
			if (debouncedSearch.trim()) {
				if (searchedDocuments?.items) {
					combinedDocs.push(...searchedDocuments.items);
					setHasMore(searchedDocuments.has_more);
				}
			} else {
				if (documents?.items) {
					combinedDocs.push(...documents.items);
					setHasMore(documents.has_more);
				}
			}

			setAccumulatedDocuments(combinedDocs);
		}
	}, [documents, searchedDocuments, surfsenseDocs, debouncedSearch, currentPage]);

	// Function to load next page
	const loadNextPage = useCallback(async () => {
		if (isLoadingMore || !hasMore) return;

		const nextPage = currentPage + 1;
		setIsLoadingMore(true);

		try {
			let response: GetDocumentsResponse;
			if (debouncedSearch.trim()) {
				const queryParams = {
					search_space_id: searchSpaceId,
					page: nextPage,
					page_size: PAGE_SIZE,
					title: debouncedSearch,
				};
				response = await documentsApiService.searchDocuments({ queryParams });
			} else {
				const queryParams = {
					search_space_id: searchSpaceId,
					page: nextPage,
					page_size: PAGE_SIZE,
				};
				response = await documentsApiService.getDocuments({ queryParams });
			}

			setAccumulatedDocuments((prev) => [...prev, ...response.items]);
			setHasMore(response.has_more);
			setCurrentPage(nextPage);
		} catch (error) {
			console.error("Failed to load next page:", error);
		} finally {
			setIsLoadingMore(false);
		}
	}, [currentPage, hasMore, isLoadingMore, debouncedSearch, searchSpaceId]);

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
	const actualLoading =
		((debouncedSearch.trim() ? isSearchedDocumentsLoading : isDocumentsLoading) ||
			isSurfsenseDocsLoading) &&
		currentPage === 0;

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

	// Scroll highlighted item into view
	useEffect(() => {
		const item = itemRefs.current.get(highlightedIndex);
		if (item) {
			item.scrollIntoView({ block: "nearest", behavior: "smooth" });
		}
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
				setHighlightedIndex((prev) => (prev > 0 ? prev - 1 : selectableDocuments.length - 1));
			},
			moveDown: () => {
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
					setHighlightedIndex((prev) => (prev < selectableDocuments.length - 1 ? prev + 1 : 0));
					break;
				case "ArrowUp":
					e.preventDefault();
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
				{actualLoading ? (
					<div className="flex items-center justify-center py-4">
						<div className="animate-spin h-5 w-5 border-2 border-primary border-t-transparent rounded-full" />
					</div>
				) : actualDocuments.length === 0 ? (
					<div className="flex flex-col items-center justify-center py-4 text-center px-4">
						<FileText className="h-5 w-5 text-muted-foreground/50 mb-1" />
						<p className="text-sm text-muted-foreground">No documents found</p>
					</div>
				) : (
					<div className="py-1">
						{actualDocuments.map((doc) => {
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
										"w-full flex items-center gap-2 px-3 py-2 text-left transition-colors",
										isAlreadySelected ? "opacity-50 cursor-not-allowed" : "cursor-pointer",
										isHighlighted && "bg-accent"
									)}
								>
									{/* Type icon */}
									<span className="flex-shrink-0 text-muted-foreground text-sm">
										{getConnectorIcon(doc.document_type)}
									</span>
									{/* Title */}
									<span className="flex-1 text-sm truncate" title={doc.title}>
										{doc.title}
									</span>
								</button>
							);
						})}
						{/* Loading indicator for additional pages */}
						{isLoadingMore && (
							<div className="flex items-center justify-center py-2">
								<div className="animate-spin h-4 w-4 border-2 border-primary border-t-transparent rounded-full" />
							</div>
						)}
					</div>
				)}
			</div>
		</div>
	);
});
