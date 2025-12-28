"use client";

import { useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";
import { RefreshCw } from "lucide-react";
import { motion } from "motion/react";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { deleteDocumentMutationAtom } from "@/atoms/documents/document-mutation.atoms";
import { documentTypeCountsAtom } from "@/atoms/documents/document-query.atoms";
import { Button } from "@/components/ui/button";
import type { DocumentTypeEnum } from "@/contracts/types/document.types";
import { useLogsSummary } from "@/hooks/use-logs";
import { documentsApiService } from "@/lib/apis/documents-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { DocumentsFilters } from "./components/DocumentsFilters";
import { DocumentsTableShell, type SortKey } from "./components/DocumentsTableShell";
import { PaginationControls } from "./components/PaginationControls";
import { ProcessingIndicator } from "./components/ProcessingIndicator";
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
	const id = useId();
	const params = useParams();
	const searchSpaceId = Number(params.search_space_id);

	const [search, setSearch] = useState("");
	const debouncedSearch = useDebounced(search, 250);
	const [activeTypes, setActiveTypes] = useState<DocumentTypeEnum[]>([]);
	const [columnVisibility, setColumnVisibility] = useState<ColumnVisibility>({
		title: true,
		document_type: true,
		content: true,
		created_at: true,
	});
	const [pageIndex, setPageIndex] = useState(0);
	const [pageSize, setPageSize] = useState(50);
	const [sortKey, setSortKey] = useState<SortKey>("title");
	const [sortDesc, setSortDesc] = useState(false);
	const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
	const { data: typeCounts } = useAtomValue(documentTypeCountsAtom);
	const { mutateAsync: deleteDocumentMutation } = useAtomValue(deleteDocumentMutationAtom);

	// Build query parameters for fetching documents
	const queryParams = useMemo(
		() => ({
			search_space_id: searchSpaceId,
			page: pageIndex,
			page_size: pageSize,
			...(activeTypes.length > 0 && { document_types: activeTypes }),
		}),
		[searchSpaceId, pageIndex, pageSize, activeTypes]
	);

	// Build search query parameters
	const searchQueryParams = useMemo(
		() => ({
			search_space_id: searchSpaceId,
			page: pageIndex,
			page_size: pageSize,
			title: debouncedSearch.trim(),
			...(activeTypes.length > 0 && { document_types: activeTypes }),
		}),
		[searchSpaceId, pageIndex, pageSize, activeTypes, debouncedSearch]
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

	// Extract documents and total based on search state
	const documents = debouncedSearch.trim()
		? searchResponse?.items || []
		: documentsResponse?.items || [];
	const total = debouncedSearch.trim() ? searchResponse?.total || 0 : documentsResponse?.total || 0;
	const loading = debouncedSearch.trim() ? isSearchLoading : isDocumentsLoading;
	const error = debouncedSearch.trim() ? searchError : documentsError;

	// Display server-filtered results directly
	const displayDocs = documents || [];
	const displayTotal = total;
	const pageStart = pageIndex * pageSize;
	const pageEnd = Math.min(pageStart + pageSize, displayTotal);

	const onToggleType = (type: DocumentTypeEnum, checked: boolean) => {
		setActiveTypes((prev) => (checked ? [...prev, type] : prev.filter((t) => t !== type)));
		setPageIndex(0);
	};

	const onToggleColumn = (id: keyof ColumnVisibility, checked: boolean) => {
		setColumnVisibility((prev) => ({ ...prev, [id]: checked }));
	};

	const refreshCurrentView = useCallback(async () => {
		if (debouncedSearch.trim()) {
			await refetchSearch();
		} else {
			await refetchDocuments();
		}
		toast.success(t("refresh_success") || "Documents refreshed");
	}, [debouncedSearch, refetchSearch, refetchDocuments, t]);

	// Set up polling for active tasks
	const { summary } = useLogsSummary(searchSpaceId, 24, { refetchInterval: 5000 });

	// Filter active tasks to only include document_processor tasks (uploads via "add sources")
	// Exclude connector_indexing_task tasks (periodic reindexing)
	const documentProcessorTasks =
		summary?.active_tasks.filter((task) => task.source === "document_processor") || [];
	const documentProcessorTasksCount = documentProcessorTasks.length;

	const activeTasksCount = summary?.active_tasks.length || 0;
	const prevActiveTasksCount = useRef(activeTasksCount);

	// Auto-refresh when a task finishes
	useEffect(() => {
		if (prevActiveTasksCount.current > activeTasksCount) {
			// A task has finished!
			refreshCurrentView();
		}
		prevActiveTasksCount.current = activeTasksCount;
	}, [activeTasksCount, refreshCurrentView]);

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

	useEffect(() => {
		const mq = window.matchMedia("(max-width: 768px)");
		const apply = (isSmall: boolean) => {
			setColumnVisibility((prev) => ({ ...prev, content: !isSmall, created_at: !isSmall }));
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
			className="w-full px-6 py-4 space-y-6 min-h-[calc(100vh-64px)]"
		>
			<motion.div
				className="flex items-center justify-between"
				initial={{ opacity: 0, y: 10 }}
				animate={{ opacity: 1, y: 0 }}
				transition={{ delay: 0.1 }}
			>
				<div>
					<h2 className="text-xl md:text-2xl font-bold tracking-tight">{t("title")}</h2>
					<p className="text-xs md:text-sm text-muted-foreground">{t("subtitle")}</p>
				</div>
				<Button onClick={refreshCurrentView} variant="outline" size="sm">
					<RefreshCw className="w-4 h-4 mr-2" />
					{t("refresh")}
				</Button>
			</motion.div>

			<ProcessingIndicator documentProcessorTasksCount={documentProcessorTasksCount} />

			<DocumentsFilters
				typeCounts={typeCounts ?? {}}
				selectedIds={selectedIds}
				onSearch={setSearch}
				searchValue={search}
				onBulkDelete={onBulkDelete}
				onToggleType={onToggleType}
				activeTypes={activeTypes}
				columnVisibility={columnVisibility}
				onToggleColumn={onToggleColumn}
			/>

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
				onSortChange={(key) => {
					if (sortKey === key) setSortDesc((v) => !v);
					else {
						setSortKey(key);
						setSortDesc(false);
					}
				}}
			/>

			<PaginationControls
				pageIndex={pageIndex}
				pageSize={pageSize}
				total={displayTotal}
				onPageSizeChange={(s) => {
					setPageSize(s);
					setPageIndex(0);
				}}
				onFirst={() => setPageIndex(0)}
				onPrev={() => setPageIndex((i) => Math.max(0, i - 1))}
				onNext={() => setPageIndex((i) => (pageEnd < displayTotal ? i + 1 : i))}
				onLast={() => setPageIndex(Math.max(0, Math.ceil(displayTotal / pageSize) - 1))}
				canPrev={pageIndex > 0}
				canNext={pageEnd < displayTotal}
				id={id}
			/>
		</motion.div>
	);
}

export { DocumentsTable };
