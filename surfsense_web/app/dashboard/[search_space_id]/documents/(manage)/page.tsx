"use client";

import { useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";
import { motion } from "motion/react";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { deleteDocumentMutationAtom } from "@/atoms/documents/document-mutation.atoms";
import { documentTypeCountsAtom } from "@/atoms/documents/document-query.atoms";
import type { DocumentTypeEnum } from "@/contracts/types/document.types";
import { documentsApiService } from "@/lib/apis/documents-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { DocumentsFilters } from "./components/DocumentsFilters";
import { DocumentsTableShell, type SortKey } from "./components/DocumentsTableShell";
import { PAGE_SIZE, PaginationControls } from "./components/PaginationControls";
import type { ColumnVisibility } from "./components/types";

function useDebounced<T>(value: T, delay = 250) {
	const [debounced, setDebounced] = useState(value);
	useEffect(() => {
		const t = setTimeout(() => setDebounced(value), delay);
		return () => clearTimeout(t);
	}, [value, delay]);
	return debounced;
}

export default function DocumentsTable() {
	const t = useTranslations("documents");
	const params = useParams();
	const searchSpaceId = Number(params.search_space_id);

	const [search, setSearch] = useState("");
	const debouncedSearch = useDebounced(search, 250);
	const [activeTypes, setActiveTypes] = useState<DocumentTypeEnum[]>([]);
	const [columnVisibility, setColumnVisibility] = useState<ColumnVisibility>({
		document_type: true,
		created_by: true,
		created_at: true,
	});
	const [pageIndex, setPageIndex] = useState(0);
	const [sortKey, setSortKey] = useState<SortKey>("created_at");
	const [sortDesc, setSortDesc] = useState(true);
	const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
	const { data: rawTypeCounts } = useAtomValue(documentTypeCountsAtom);
	const { mutateAsync: deleteDocumentMutation } = useAtomValue(deleteDocumentMutationAtom);

	// Build query parameters for fetching documents
	const queryParams = useMemo(
		() => ({
			search_space_id: searchSpaceId,
			page: pageIndex,
			page_size: PAGE_SIZE,
			...(activeTypes.length > 0 && { document_types: activeTypes }),
		}),
		[searchSpaceId, pageIndex, activeTypes]
	);

	// Build search query parameters
	const searchQueryParams = useMemo(
		() => ({
			search_space_id: searchSpaceId,
			page: pageIndex,
			page_size: PAGE_SIZE,
			title: debouncedSearch.trim(),
			...(activeTypes.length > 0 && { document_types: activeTypes }),
		}),
		[searchSpaceId, pageIndex, activeTypes, debouncedSearch]
	);

	// Use query for fetching documents
	const {
		data: documentsResponse,
		isLoading: isDocumentsLoading,
		refetch: refetchDocuments,
		error: documentsError,
	} = useQuery({
		queryKey: cacheKeys.documents.globalQueryParams(queryParams),
		queryFn: () => documentsApiService.getDocuments({ queryParams }),
		staleTime: 3 * 60 * 1000, // 3 minutes
		enabled: !!searchSpaceId && !debouncedSearch.trim(),
	});

	// Use query for searching documents
	const {
		data: searchResponse,
		isLoading: isSearchLoading,
		refetch: refetchSearch,
		error: searchError,
	} = useQuery({
		queryKey: cacheKeys.documents.globalQueryParams(searchQueryParams),
		queryFn: () => documentsApiService.searchDocuments({ queryParams: searchQueryParams }),
		staleTime: 3 * 60 * 1000, // 3 minutes
		enabled: !!searchSpaceId && !!debouncedSearch.trim(),
	});

	// Determine if we should show SurfSense docs (when no type filter or SURFSENSE_DOCS is selected)
	const showSurfsenseDocs =
		activeTypes.length === 0 || activeTypes.includes("SURFSENSE_DOCS" as DocumentTypeEnum);

	// Use query for fetching SurfSense docs
	// eslint-disable-next-line @typescript-eslint/no-unused-vars
	const { data: surfsenseDocsResponse } = useQuery({
		queryKey: ["surfsense-docs", debouncedSearch, pageIndex, PAGE_SIZE],
		queryFn: () =>
			documentsApiService.getSurfsenseDocs({
				queryParams: {
					page: pageIndex,
					page_size: PAGE_SIZE,
					title: debouncedSearch.trim() || undefined,
				},
			}),
		staleTime: 3 * 60 * 1000, // 3 minutes
		enabled: showSurfsenseDocs,
	});

	// Transform SurfSense docs to match the Document type
	// eslint-disable-next-line @typescript-eslint/no-unused-vars
	const surfsenseDocsAsDocuments = useMemo(() => {
		if (!surfsenseDocsResponse?.items) return [];
		return surfsenseDocsResponse.items.map((doc) => ({
			id: doc.id,
			title: doc.title,
			document_type: "SURFSENSE_DOCS",
			document_metadata: { source: doc.source },
			content: doc.content,
			created_at: new Date().toISOString(),
			search_space_id: -1, // Special value for global docs
		}));
	}, [surfsenseDocsResponse]);

	// Merge type counts with SURFSENSE_DOCS count
	// eslint-disable-next-line @typescript-eslint/no-unused-vars
	const typeCounts = useMemo(() => {
		const counts = { ...(rawTypeCounts || {}) };
		if (surfsenseDocsResponse?.total) {
			counts.SURFSENSE_DOCS = surfsenseDocsResponse.total;
		}
		return counts;
	}, [rawTypeCounts, surfsenseDocsResponse?.total]);

	// Extract documents and total based on search state
	const documents = debouncedSearch.trim()
		? searchResponse?.items || []
		: documentsResponse?.items || [];
	const total = debouncedSearch.trim() ? searchResponse?.total || 0 : documentsResponse?.total || 0;

	const loading = debouncedSearch.trim() ? isSearchLoading : isDocumentsLoading;
	const error = debouncedSearch.trim() ? searchError : documentsError;

	// Display results directly
	const displayDocs = documents;
	const displayTotal = total;
	const pageEnd = Math.min((pageIndex + 1) * PAGE_SIZE, displayTotal);

	const onToggleType = (type: DocumentTypeEnum, checked: boolean) => {
		setActiveTypes((prev) => {
			if (checked) {
				// Only add if not already in the array
				return prev.includes(type) ? prev : [...prev, type];
			} else {
				return prev.filter((t) => t !== type);
			}
		});
		setPageIndex(0);
	};

	const onToggleColumn = (id: keyof ColumnVisibility, checked: boolean) => {
		setColumnVisibility((prev) => ({ ...prev, [id]: checked }));
	};

	const [isRefreshing, setIsRefreshing] = useState(false);

	const refreshCurrentView = useCallback(async () => {
		if (isRefreshing) return;
		setIsRefreshing(true);
		try {
			if (debouncedSearch.trim()) {
				await refetchSearch();
			} else {
				await refetchDocuments();
			}
			toast.success(t("refresh_success") || "Documents refreshed");
		} finally {
			setIsRefreshing(false);
		}
	}, [debouncedSearch, refetchSearch, refetchDocuments, t, isRefreshing]);

	// Create a delete function for single document deletion
	const deleteDocument = useCallback(
		async (id: number) => {
			try {
				await deleteDocumentMutation({ id });
				return true;
			} catch (error) {
				console.error("Failed to delete document:", error);
				return false;
			}
		},
		[deleteDocumentMutation]
	);

	const onBulkDelete = async () => {
		if (selectedIds.size === 0) {
			toast.error(t("no_rows_selected"));
			return;
		}
		try {
			// Delete documents one by one using the mutation
			const results = await Promise.all(
				Array.from(selectedIds).map(async (id) => {
					try {
						await deleteDocumentMutation({ id });
						return true;
					} catch {
						return false;
					}
				})
			);
			const okCount = results.filter((r) => r === true).length;
			if (okCount === selectedIds.size)
				toast.success(t("delete_success_count", { count: okCount }));
			else toast.error(t("delete_partial_failed"));
			// Refetch the current page with appropriate method
			await refreshCurrentView();
			setSelectedIds(new Set());
		} catch (e) {
			console.error(e);
			toast.error(t("delete_error"));
		}
	};

	const handleSortChange = useCallback((key: SortKey) => {
		setSortKey((currentKey) => {
			if (currentKey === key) {
				setSortDesc((v) => !v);
				return currentKey;
			}
			setSortDesc(false);
			return key;
		});
	}, []);

	useEffect(() => {
		const mq = window.matchMedia("(max-width: 768px)");
		const apply = (isSmall: boolean) => {
			setColumnVisibility((prev) => ({ ...prev, created_by: !isSmall, created_at: !isSmall }));
		};
		apply(mq.matches);
		const onChange = (e: MediaQueryListEvent) => apply(e.matches);
		mq.addEventListener("change", onChange);
		return () => mq.removeEventListener("change", onChange);
	}, []);

	return (
		<motion.div
			initial={{ opacity: 0, y: 20 }}
			animate={{ opacity: 1, y: 0 }}
			transition={{ duration: 0.3 }}
			className="w-full max-w-7xl mx-auto px-6 pt-17 pb-6 space-y-6 min-h-[calc(100vh-64px)]"
		>
			{/* Filters */}
			<DocumentsFilters
				typeCounts={rawTypeCounts ?? {}}
				selectedIds={selectedIds}
				onSearch={setSearch}
				searchValue={search}
				onBulkDelete={onBulkDelete}
				onToggleType={onToggleType}
				activeTypes={activeTypes}
				columnVisibility={columnVisibility}
				onToggleColumn={onToggleColumn}
			/>

			{/* Table */}
			<DocumentsTableShell
				documents={displayDocs}
				loading={!!loading}
				error={!!error}
				onRefresh={refreshCurrentView}
				selectedIds={selectedIds}
				setSelectedIds={setSelectedIds}
				columnVisibility={columnVisibility}
				deleteDocument={deleteDocument}
				sortKey={sortKey}
				sortDesc={sortDesc}
				onSortChange={handleSortChange}
			/>

			{/* Pagination */}
			<PaginationControls
				pageIndex={pageIndex}
				total={displayTotal}
				onFirst={() => setPageIndex(0)}
				onPrev={() => setPageIndex((i) => Math.max(0, i - 1))}
				onNext={() => setPageIndex((i) => (pageEnd < displayTotal ? i + 1 : i))}
				onLast={() => setPageIndex(Math.max(0, Math.ceil(displayTotal / PAGE_SIZE) - 1))}
				canPrev={pageIndex > 0}
				canNext={pageEnd < displayTotal}
			/>
		</motion.div>
	);
}

export { DocumentsTable };
