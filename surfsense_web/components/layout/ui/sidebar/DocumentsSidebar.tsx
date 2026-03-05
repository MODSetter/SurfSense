"use client";

import { useAtomValue } from "jotai";
import { ChevronLeft, SquareLibrary } from "lucide-react";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { deleteDocumentMutationAtom } from "@/atoms/documents/document-mutation.atoms";
import { Button } from "@/components/ui/button";
import type { DocumentTypeEnum } from "@/contracts/types/document.types";
import { useDocuments } from "@/hooks/use-documents";
import { documentsApiService } from "@/lib/apis/documents-api.service";
import { useMediaQuery } from "@/hooks/use-media-query";
import {
	DocumentsFilters,
} from "@/app/dashboard/[search_space_id]/documents/(manage)/components/DocumentsFilters";
import {
	DocumentsTableShell,
	type SortKey,
} from "@/app/dashboard/[search_space_id]/documents/(manage)/components/DocumentsTableShell";
import type { ColumnVisibility } from "@/app/dashboard/[search_space_id]/documents/(manage)/components/types";
import { SidebarSlideOutPanel } from "./SidebarSlideOutPanel";

const INITIAL_LOAD_SIZE = 20;
const SCROLL_LOAD_SIZE = 5;

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

	// --- Infinite scroll state ---
	const [visibleCount, setVisibleCount] = useState(INITIAL_LOAD_SIZE);
	const [searchItems, setSearchItems] = useState<Array<{
		id: number;
		search_space_id: number;
		document_type: string;
		title: string;
		created_by_id: string | null;
		created_by_name: string | null;
		created_by_email: string | null;
		created_at: string;
		status: { state: "ready" | "pending" | "processing" | "failed"; reason?: string };
	}>>([]);
	const [searchTotal, setSearchTotal] = useState(0);
	const [searchPageIndex, setSearchPageIndex] = useState(0);
	const [searchLoadingMore, setSearchLoadingMore] = useState(false);
	const [searchInitialLoading, setSearchInitialLoading] = useState(false);
	const searchQueryRef = useRef(debouncedSearch);

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

	// Reset visible count when sort/filter changes
	// biome-ignore lint/correctness/useExhaustiveDependencies: intentional reset
	useEffect(() => {
		setVisibleCount(INITIAL_LOAD_SIZE);
	}, [sortKey, sortDesc, activeTypes]);

	// Initial search fetch when search query changes
	useEffect(() => {
		if (!isSearchMode || !searchSpaceId || !open) {
			setSearchItems([]);
			setSearchTotal(0);
			setSearchPageIndex(0);
			return;
		}

		searchQueryRef.current = debouncedSearch;
		setSearchInitialLoading(true);

		const queryParams = {
			search_space_id: searchSpaceId,
			page: 0,
			page_size: INITIAL_LOAD_SIZE,
			title: debouncedSearch.trim(),
			...(activeTypes.length > 0 && { document_types: activeTypes }),
		};

		documentsApiService
			.searchDocuments({ queryParams })
			.then((response) => {
				if (searchQueryRef.current !== debouncedSearch) return;
				const mapped = response.items.map((item) => ({
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
				}));
				setSearchItems(mapped);
				setSearchTotal(response.total);
				setSearchPageIndex(0);
			})
			.catch((err) => {
				console.error("[DocumentsSidebar] Search failed:", err);
			})
			.finally(() => {
				setSearchInitialLoading(false);
			});
	}, [debouncedSearch, searchSpaceId, open, isSearchMode, activeTypes]);

	// Load more search results
	const loadMoreSearch = useCallback(async () => {
		if (searchLoadingMore || !isSearchMode) return;
		const nextPage = searchPageIndex + 1;
		if (searchItems.length >= searchTotal) return;

		setSearchLoadingMore(true);
		try {
			const queryParams = {
				search_space_id: searchSpaceId,
				page: nextPage,
				page_size: SCROLL_LOAD_SIZE,
				title: debouncedSearch.trim(),
				...(activeTypes.length > 0 && { document_types: activeTypes }),
			};
			const response = await documentsApiService.searchDocuments({ queryParams });
			if (searchQueryRef.current !== debouncedSearch) return;

			const mapped = response.items.map((item) => ({
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
			}));
			setSearchItems((prev) => [...prev, ...mapped]);
			setSearchTotal(response.total);
			setSearchPageIndex(nextPage);
		} catch (err) {
			console.error("[DocumentsSidebar] Load more search failed:", err);
		} finally {
			setSearchLoadingMore(false);
		}
	}, [searchLoadingMore, isSearchMode, searchPageIndex, searchItems.length, searchTotal, searchSpaceId, debouncedSearch, activeTypes]);

	// Load more for realtime (client-side, just increase visible count)
	const loadMoreRealtime = useCallback(() => {
		setVisibleCount((prev) => Math.min(prev + SCROLL_LOAD_SIZE, sortedRealtimeDocuments.length));
	}, [sortedRealtimeDocuments.length]);

	const visibleRealtimeDocs = useMemo(
		() => sortedRealtimeDocuments.slice(0, visibleCount),
		[sortedRealtimeDocuments, visibleCount]
	);

	const displayDocs = isSearchMode ? searchItems : visibleRealtimeDocs;
	const loading = isSearchMode ? searchInitialLoading : realtimeLoading;
	const error = isSearchMode ? false : realtimeError;

	const hasMore = isSearchMode
		? searchItems.length < searchTotal
		: visibleCount < sortedRealtimeDocuments.length;

	const loadingMore = isSearchMode ? searchLoadingMore : false;

	const onLoadMore = isSearchMode ? loadMoreSearch : loadMoreRealtime;

	const onToggleType = (type: DocumentTypeEnum, checked: boolean) => {
		setActiveTypes((prev) => {
			if (checked) {
				return prev.includes(type) ? prev : [...prev, type];
			}
			return prev.filter((t) => t !== type);
		});
		setSelectedIds(new Set());
	};

	const onBulkDelete = async () => {
		if (selectedIds.size === 0) {
			toast.error(t("no_rows_selected"));
			return;
		}

		const allDocs = isSearchMode
			? searchItems.map((item) => ({ id: item.id, status: item.status }))
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
			if (isSearchMode) {
				setSearchItems((prev) => prev.filter((item) => !deletableIds.includes(item.id)));
				setSearchTotal((prev) => prev - okCount);
			}
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
				if (isSearchMode) {
					setSearchItems((prev) => prev.filter((item) => item.id !== id));
					setSearchTotal((prev) => prev - 1);
				}
				return true;
			} catch (e) {
				console.error("Error deleting document:", e);
				return false;
			}
		},
		[deleteDocumentMutation, isSearchMode, t]
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

			<div className="flex-1 min-h-0 overflow-x-hidden pt-0 flex flex-col">
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
					hasMore={hasMore}
					loadingMore={loadingMore}
					onLoadMore={onLoadMore}
				/>
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
