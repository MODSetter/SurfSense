"use client";

import { useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";
import { ChevronLeft, SquareLibrary } from "lucide-react";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { deleteDocumentMutationAtom } from "@/atoms/documents/document-mutation.atoms";
import { Button } from "@/components/ui/button";
import type { DocumentTypeEnum } from "@/contracts/types/document.types";
import { useDocuments } from "@/hooks/use-documents";
import { documentsApiService } from "@/lib/apis/documents-api.service";
import { useMediaQuery } from "@/hooks/use-media-query";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import {
	DocumentsFilters,
} from "@/app/dashboard/[search_space_id]/documents/(manage)/components/DocumentsFilters";
import {
	DocumentsTableShell,
	type SortKey,
} from "@/app/dashboard/[search_space_id]/documents/(manage)/components/DocumentsTableShell";
import {
	PAGE_SIZE,
	PaginationControls,
} from "@/app/dashboard/[search_space_id]/documents/(manage)/components/PaginationControls";
import type { ColumnVisibility } from "@/app/dashboard/[search_space_id]/documents/(manage)/components/types";
import { SidebarSlideOutPanel } from "./SidebarSlideOutPanel";

function useDebounced<T>(value: T, delay = 250) {
	const [debounced, setDebounced] = useState(value);
	useEffect(() => {
		const t = setTimeout(() => setDebounced(value), delay);
		return () => clearTimeout(t);
	}, [value, delay]);
	return debounced;
}

interface DocumentsSidebarProps {
	open: boolean;
	onOpenChange: (open: boolean) => void;
}

export function DocumentsSidebar({ open, onOpenChange }: DocumentsSidebarProps) {
	const t = useTranslations("documents");
	const tSidebar = useTranslations("sidebar");
	const params = useParams();
	const isMobile = !useMediaQuery("(min-width: 640px)");
	const searchSpaceId = Number(params.search_space_id);

	const [search, setSearch] = useState("");
	const debouncedSearch = useDebounced(search, 250);
	const [activeTypes, setActiveTypes] = useState<DocumentTypeEnum[]>([]);
	const [columnVisibility, setColumnVisibility] = useState<ColumnVisibility>({
		document_type: true,
		created_by: false,
		created_at: true,
		status: true,
	});
	const [pageIndex, setPageIndex] = useState(0);
	const [sortKey, setSortKey] = useState<SortKey>("created_at");
	const [sortDesc, setSortDesc] = useState(true);
	const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
	const { mutateAsync: deleteDocumentMutation } = useAtomValue(deleteDocumentMutationAtom);

	const {
		documents: realtimeDocuments,
		typeCounts: realtimeTypeCounts,
		loading: realtimeLoading,
		error: realtimeError,
	} = useDocuments(searchSpaceId, activeTypes);

	const isSearchMode = !!debouncedSearch.trim();

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

	const {
		data: searchResponse,
		isLoading: isSearchLoading,
		refetch: refetchSearch,
		error: searchError,
	} = useQuery({
		queryKey: cacheKeys.documents.globalQueryParams(searchQueryParams),
		queryFn: () => documentsApiService.searchDocuments({ queryParams: searchQueryParams }),
		staleTime: 30 * 1000,
		enabled: !!searchSpaceId && isSearchMode && open,
	});

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

	const paginatedRealtimeDocuments = useMemo(() => {
		const start = pageIndex * PAGE_SIZE;
		const end = start + PAGE_SIZE;
		return sortedRealtimeDocuments.slice(start, end);
	}, [sortedRealtimeDocuments, pageIndex]);

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
			}
			return prev.filter((t) => t !== type);
		});
		setPageIndex(0);
		setSelectedIds(new Set());
	};

	const onBulkDelete = async () => {
		if (selectedIds.size === 0) {
			toast.error(t("no_rows_selected"));
			return;
		}

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

		if (deletableIds.length === 0) return;

		try {
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
			if (isSearchMode) await refetchSearch();
			setSelectedIds(new Set());
		} catch (e) {
			console.error(e);
			toast.error(t("delete_error"));
		}
	};

	const handleDeleteDocument = useCallback(
		async (id: number): Promise<boolean> => {
			try {
				await deleteDocumentMutation({ id });
				toast.success(t("delete_success") || "Document deleted");
				if (isSearchMode) await refetchSearch();
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

	// biome-ignore lint/correctness/useExhaustiveDependencies: Reset page on search change
	useEffect(() => {
		setPageIndex(0);
	}, [debouncedSearch]);

	useEffect(() => {
		if (!open) return;
		const panelWidth = isMobile ? window.innerWidth : 720;
		const isNarrow = panelWidth < 600;
		setColumnVisibility((prev) => ({ ...prev, created_by: !isNarrow, created_at: !isNarrow }));
	}, [open, isMobile]);

	useEffect(() => {
		const handleEscape = (e: KeyboardEvent) => {
			if (e.key === "Escape" && open) {
				onOpenChange(false);
			}
		};
		document.addEventListener("keydown", handleEscape);
		return () => document.removeEventListener("keydown", handleEscape);
	}, [open, onOpenChange]);

	const documentsContent = (
		<>
			<div className="shrink-0 p-4 pb-2">
				<div className="flex items-center justify-between">
					<div className="flex items-center gap-2">
						{isMobile && (
							<Button
								variant="ghost"
								size="icon"
								className="h-8 w-8 rounded-full"
								onClick={() => onOpenChange(false)}
							>
								<ChevronLeft className="h-4 w-4 text-muted-foreground" />
								<span className="sr-only">{tSidebar("close") || "Close"}</span>
							</Button>
						)}
						<SquareLibrary className="h-5 w-5 text-muted-foreground" />
						<h2 className="text-lg font-semibold">{t("title") || "Documents"}</h2>
					</div>
				</div>
			</div>

			<div className="flex-1 overflow-y-auto overflow-x-hidden pt-0">
				<div className="px-4 pb-2">
					<DocumentsFilters
						typeCounts={realtimeTypeCounts}
						selectedIds={selectedIds}
						onSearch={setSearch}
						searchValue={search}
						onBulkDelete={onBulkDelete}
						onToggleType={onToggleType}
						activeTypes={activeTypes}
					/>
				</div>

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

				<div className="px-4 py-2">
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
				</div>
			</div>
		</>
	);

	return (
		<SidebarSlideOutPanel
			open={open}
			onOpenChange={onOpenChange}
			ariaLabel={t("title") || "Documents"}
			width={isMobile ? undefined : 480}
		>
			{documentsContent}
		</SidebarSlideOutPanel>
	);
}
