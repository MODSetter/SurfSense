"use client";

import { useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";
import { RefreshCw, SquarePlus, Upload } from "lucide-react";
import { motion } from "motion/react";
import { useParams, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useId, useMemo, useState } from "react";
import { toast } from "sonner";
import { deleteDocumentMutationAtom } from "@/atoms/documents/document-mutation.atoms";
import { documentTypeCountsAtom } from "@/atoms/documents/document-query.atoms";
import { useDocumentUploadDialog } from "@/components/assistant-ui/document-upload-popup";
import { Button } from "@/components/ui/button";
import type { DocumentTypeEnum } from "@/contracts/types/document.types";
import { documentsApiService } from "@/lib/apis/documents-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { DocumentsFilters } from "./components/DocumentsFilters";
import { DocumentsTableShell, type SortKey } from "./components/DocumentsTableShell";
import { PaginationControls } from "./components/PaginationControls";
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
	const router = useRouter();
	const searchSpaceId = Number(params.search_space_id);
	const { openDialog: openUploadDialog } = useDocumentUploadDialog();

	const handleNewNote = useCallback(() => {
		router.push(`/dashboard/${searchSpaceId}/editor/new`);
	}, [router, searchSpaceId]);

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
	const { data: rawTypeCounts } = useAtomValue(documentTypeCountsAtom);
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

	// Determine if we should show SurfSense docs (when no type filter or SURFSENSE_DOCS is selected)
	const showSurfsenseDocs =
		activeTypes.length === 0 || activeTypes.includes("SURFSENSE_DOCS" as DocumentTypeEnum);

	// Use query for fetching SurfSense docs
	const {
		data: surfsenseDocsResponse,
		isLoading: isSurfsenseDocsLoading,
		refetch: refetchSurfsenseDocs,
	} = useQuery({
		queryKey: ["surfsense-docs", debouncedSearch, pageIndex, pageSize],
		queryFn: () =>
			documentsApiService.getSurfsenseDocs({
				queryParams: {
					page: pageIndex,
					page_size: pageSize,
					title: debouncedSearch.trim() || undefined,
				},
			}),
		staleTime: 3 * 60 * 1000, // 3 minutes
		enabled: showSurfsenseDocs,
	});

	// Transform SurfSense docs to match the Document type
	const surfsenseDocsAsDocuments: Document[] = useMemo(() => {
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
	const pageStart = pageIndex * pageSize;
	const pageEnd = Math.min(pageStart + pageSize, displayTotal);

	const onToggleType = (type: DocumentTypeEnum, checked: boolean) => {
		setActiveTypes((prev) => (checked ? [...prev, type] : prev.filter((t) => t !== type)));
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
				<div className="flex items-center gap-2">
					<Button onClick={openUploadDialog} variant="default" size="sm">
						<Upload className="w-4 h-4 mr-2" />
						{t("upload_documents")}
					</Button>
					<Button onClick={handleNewNote} variant="outline" size="sm">
						<SquarePlus className="w-4 h-4 mr-2" />
						{t("create_shared_note")}
					</Button>
					<Button onClick={refreshCurrentView} variant="outline" size="sm" disabled={isRefreshing}>
						<RefreshCw className={`w-4 h-4 mr-2 ${isRefreshing ? "animate-spin" : ""}`} />
						{t("refresh")}
					</Button>
				</div>
			</motion.div>

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
