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
import type { Document } from "@/contracts/types/document.types";
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
	onSelectionChange: (documents: Document[]) => void;
	onDone: () => void;
	initialSelectedDocuments?: Document[];
	externalSearch?: string;
}

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

	const fetchQueryParams = useMemo(
		() => ({
			search_space_id: searchSpaceId,
			page: 0,
			page_size: 20,
		}),
		[searchSpaceId]
	);

	const searchQueryParams = useMemo(() => {
		return {
			search_space_id: searchSpaceId,
			page: 0,
			page_size: 20,
			title: debouncedSearch,
		};
	}, [debouncedSearch, searchSpaceId]);

	// Use query for fetching documents
	const { data: documents, isLoading: isDocumentsLoading } = useQuery({
		queryKey: cacheKeys.documents.withQueryParams(fetchQueryParams),
		queryFn: () => documentsApiService.getDocuments({ queryParams: fetchQueryParams }),
		staleTime: 3 * 60 * 1000,
		enabled: !!searchSpaceId && !debouncedSearch.trim(),
	});

	// Searching
	const { data: searchedDocuments, isLoading: isSearchedDocumentsLoading } = useQuery({
		queryKey: cacheKeys.documents.withQueryParams(searchQueryParams),
		queryFn: () => documentsApiService.searchDocuments({ queryParams: searchQueryParams }),
		staleTime: 3 * 60 * 1000,
		enabled: !!searchSpaceId && !!debouncedSearch.trim(),
	});

	const actualDocuments = debouncedSearch.trim()
		? searchedDocuments?.items || []
		: documents?.items || [];
	const actualLoading = debouncedSearch.trim() ? isSearchedDocumentsLoading : isDocumentsLoading;

	// Track already selected document IDs
	const selectedIds = useMemo(
		() => new Set(initialSelectedDocuments.map((d) => d.id)),
		[initialSelectedDocuments]
	);

	// Filter out already selected documents for navigation
	const selectableDocuments = useMemo(
		() => actualDocuments.filter((doc) => !selectedIds.has(doc.id)),
		[actualDocuments, selectedIds]
	);

	const handleSelectDocument = useCallback(
		(doc: Document) => {
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
			{/* Document List */}
			<div className="max-h-[280px] overflow-y-auto">
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
							const isAlreadySelected = selectedIds.has(doc.id);
							const selectableIndex = selectableDocuments.findIndex((d) => d.id === doc.id);
							const isHighlighted = !isAlreadySelected && selectableIndex === highlightedIndex;

							return (
								<button
									key={doc.id}
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
					</div>
				)}
			</div>
		</div>
	);
});
