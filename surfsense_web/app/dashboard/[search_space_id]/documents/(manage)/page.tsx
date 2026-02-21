"use client";

import { useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";
import { motion } from "motion/react";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { deleteDocumentMutationAtom } from "@/atoms/documents/document-mutation.atoms";
import type { DocumentTypeEnum } from "@/contracts/types/document.types";
import { useDocuments } from "@/hooks/use-documents";
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
		status: true,
	});
	const [pageIndex, setPageIndex] = useState(0);
	const [sortKey, setSortKey] = useState<SortKey>("created_at");
	const [sortDesc, setSortDesc] = useState(true);
	const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
	const { mutateAsync: deleteDocumentMutation } = useAtomValue(deleteDocumentMutationAtom);

	// REAL-TIME: Use Electric SQL hook for live document updates (when not searching)
	const {
		documents: realtimeDocuments,
		typeCounts: realtimeTypeCounts,
		loading: realtimeLoading,
		error: realtimeError,
	} = useDocuments(searchSpaceId, activeTypes);

	// Check if we're in search mode
	const isSearchMode = !!debouncedSearch.trim();

	// Build search query parameters (only used when searching)
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

	// API search query (only enabled when searching - Electric doesn't do full-text search)
	const {
		data: searchResponse,
		isLoading: isSearchLoading,
		refetch: refetchSearch,
		error: searchError,
	} = useQuery({
		queryKey: cacheKeys.documents.globalQueryParams(searchQueryParams),
		queryFn: () => documentsApiService.searchDocuments({ queryParams: searchQueryParams }),
		staleTime: 30 * 1000, // 30 seconds for search (shorter since it's on-demand)
		enabled: !!searchSpaceId && isSearchMode,
	});

	// Client-side sorting for real-time documents
	const sortedRealtimeDocuments = useMemo(() => {
		const docs = [...realtimeDocuments];
		docs.sort((a, b) => {
			const av = a[sortKey] ?? "";
			const bv = b[sortKey] ?? "";
			let cmp: number;
			if (sortKey === "created_at") {
				cmp = new Date(av as string).getTime() - new Date(bv as string).getTime();
			} else {
				cmp = String(av).localeCompare(String(bv));
			}
			return sortDesc ? -cmp : cmp;
		});
		return docs;
	}, [realtimeDocuments, sortKey, sortDesc]);

	// Client-side pagination for real-time documents
	const paginatedRealtimeDocuments = useMemo(() => {
		const start = pageIndex * PAGE_SIZE;
		const end = start + PAGE_SIZE;
		return sortedRealtimeDocuments.slice(start, end);
	}, [sortedRealtimeDocuments, pageIndex]);

	// Determine what to display based on search mode
	const displayDocs = isSearchMode
		? (searchResponse?.items || []).map((item) => ({
				id: item.id,
				search_space_id: item.search_space_id,
				document_type: item.document_type,
				title: item.title,
				created_by_id: item.created_by_id ?? null,
				created_by_name: item.created_by_name ?? null,
				created_by_email: item.created_by_email ?? null,
				created_at: item.created_at,
				status: (
					item as {
						status?: { state: "ready" | "pending" | "processing" | "failed"; reason?: string };
					}
				).status ?? { state: "ready" as const },
			}))
		: paginatedRealtimeDocuments;

	const displayTotal = isSearchMode ? searchResponse?.total || 0 : sortedRealtimeDocuments.length;

	const loading = isSearchMode ? isSearchLoading : realtimeLoading;
	const error = isSearchMode ? searchError : realtimeError;

	const pageEnd = Math.min((pageIndex + 1) * PAGE_SIZE, displayTotal);

	const onToggleType = (type: DocumentTypeEnum, checked: boolean) => {
		setActiveTypes((prev) => {
			if (checked) {
				return prev.includes(type) ? prev : [...prev, type];
			} else {
				return prev.filter((t) => t !== type);
			}
		});
		setPageIndex(0);
		// Clear selections when filter changes — selected IDs from the previous
		// filter view are no longer visible and would cause misleading bulk actions
		setSelectedIds(new Set());
	};

	const onBulkDelete = async () => {
		if (selectedIds.size === 0) {
			toast.error(t("no_rows_selected"));
			return;
		}

		// Filter out pending/processing documents - they cannot be deleted
		// For real-time mode, use sortedRealtimeDocuments (which has status)
		// For search mode, use searchResponse items (need to safely access status)
		const allDocs = isSearchMode
			? (searchResponse?.items || []).map((item) => ({
					id: item.id,
					status: (item as { status?: { state: string } }).status,
				}))
			: sortedRealtimeDocuments.map((doc) => ({ id: doc.id, status: doc.status }));

		const selectedDocs = allDocs.filter((doc) => selectedIds.has(doc.id));
		const deletableIds = selectedDocs
			.filter((doc) => doc.status?.state !== "pending" && doc.status?.state !== "processing")
			.map((doc) => doc.id);
		const inProgressCount = selectedIds.size - deletableIds.length;

		if (inProgressCount > 0) {
			toast.warning(
				`${inProgressCount} document(s) are pending or processing and cannot be deleted.`
			);
		}

		if (deletableIds.length === 0) {
			return;
		}

		try {
			// Delete documents one by one using the mutation
			// Track 409 conflicts separately (document started processing after UI loaded)
			let conflictCount = 0;
			const results = await Promise.all(
				deletableIds.map(async (id) => {
					try {
						await deleteDocumentMutation({ id });
						return true;
					} catch (error: unknown) {
						const status =
							(error as { response?: { status?: number } })?.response?.status ??
							(error as { status?: number })?.status;
						if (status === 409) conflictCount++;
						return false;
					}
				})
			);
			const okCount = results.filter((r) => r === true).length;
			if (okCount === deletableIds.length) {
				toast.success(t("delete_success_count", { count: okCount }));
			} else if (conflictCount > 0) {
				toast.error(`${conflictCount} document(s) started processing. Please try again later.`);
			} else {
				toast.error(t("delete_partial_failed"));
			}

			// If in search mode, refetch search results to reflect deletion
			if (isSearchMode) {
				await refetchSearch();
			}
			// Real-time mode: Electric will sync the deletion automatically

			setSelectedIds(new Set());
		} catch (e) {
			console.error(e);
			toast.error(t("delete_error"));
		}
	};

	// Single document delete handler for RowActions
	const handleDeleteDocument = useCallback(
		async (id: number): Promise<boolean> => {
			try {
				await deleteDocumentMutation({ id });
				toast.success(t("delete_success") || "Document deleted");
				// If in search mode, refetch search results to reflect deletion
				if (isSearchMode) {
					await refetchSearch();
				}
				// Real-time mode: Electric will sync the deletion automatically
				return true;
			} catch (e) {
				console.error("Error deleting document:", e);
				return false;
			}
		},
		[deleteDocumentMutation, isSearchMode, refetchSearch, t]
	);

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

	// Reset page when search changes (type filter already resets via onToggleType)
	// biome-ignore lint/correctness/useExhaustiveDependencies: Intentionally reset page on search change
	useEffect(() => {
		setPageIndex(0);
	}, [debouncedSearch]);

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
			{/* Filters - use real-time type counts */}
			<DocumentsFilters
				typeCounts={realtimeTypeCounts}
				selectedIds={selectedIds}
				onSearch={setSearch}
				searchValue={search}
				onBulkDelete={onBulkDelete}
				onToggleType={onToggleType}
				activeTypes={activeTypes}
			/>

			{/* Table */}
			<DocumentsTableShell
				documents={displayDocs}
				loading={!!loading}
				error={!!error}
				selectedIds={selectedIds}
				setSelectedIds={setSelectedIds}
				columnVisibility={columnVisibility}
				sortKey={sortKey}
				sortDesc={sortDesc}
				onSortChange={handleSortChange}
				deleteDocument={handleDeleteDocument}
				searchSpaceId={String(searchSpaceId)}
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
