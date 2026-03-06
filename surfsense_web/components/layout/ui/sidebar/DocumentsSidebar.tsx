"use client";

import { useAtomValue } from "jotai";
import { ChevronLeft } from "lucide-react";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { deleteDocumentMutationAtom } from "@/atoms/documents/document-mutation.atoms";
import { Button } from "@/components/ui/button";
import type { DocumentTypeEnum } from "@/contracts/types/document.types";
import { useDocuments } from "@/hooks/use-documents";
import { useDocumentSearch } from "@/hooks/use-document-search";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { useMediaQuery } from "@/hooks/use-media-query";
import { DocumentsFilters } from "@/app/dashboard/[search_space_id]/documents/(manage)/components/DocumentsFilters";
import {
	DocumentsTableShell,
	type SortKey,
} from "@/app/dashboard/[search_space_id]/documents/(manage)/components/DocumentsTableShell";
import { SidebarSlideOutPanel } from "./SidebarSlideOutPanel";

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
	const debouncedSearch = useDebouncedValue(search, 250);
	const [activeTypes, setActiveTypes] = useState<DocumentTypeEnum[]>([]);
	const [sortKey, setSortKey] = useState<SortKey>("created_at");
	const [sortDesc, setSortDesc] = useState(true);
	const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
	const { mutateAsync: deleteDocumentMutation } = useAtomValue(deleteDocumentMutationAtom);

	const isSearchMode = !!debouncedSearch.trim();

	const {
		documents: realtimeDocuments,
		typeCounts: realtimeTypeCounts,
		loading: realtimeLoading,
		loadingMore: realtimeLoadingMore,
		hasMore: realtimeHasMore,
		loadMore: realtimeLoadMore,
		error: realtimeError,
	} = useDocuments(searchSpaceId, activeTypes, sortKey, sortDesc ? "desc" : "asc");

	const {
		documents: searchDocuments,
		loading: searchLoading,
		loadingMore: searchLoadingMore,
		hasMore: searchHasMore,
		loadMore: searchLoadMore,
		error: searchError,
		removeItems: searchRemoveItems,
	} = useDocumentSearch(searchSpaceId, debouncedSearch, activeTypes, isSearchMode && open);

	const displayDocs = isSearchMode ? searchDocuments : realtimeDocuments;
	const loading = isSearchMode ? searchLoading : realtimeLoading;
	const error = isSearchMode ? searchError : !!realtimeError;
	const hasMore = isSearchMode ? searchHasMore : realtimeHasMore;
	const loadingMore = isSearchMode ? searchLoadingMore : realtimeLoadingMore;
	const onLoadMore = isSearchMode ? searchLoadMore : realtimeLoadMore;

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

		const selectedDocs = displayDocs.filter((doc) => selectedIds.has(doc.id));
		const deletableIds = selectedDocs
			.filter((doc) => doc.status?.state !== "pending" && doc.status?.state !== "processing")
			.map((doc) => doc.id);
		const inProgressCount = selectedIds.size - deletableIds.length;

		if (inProgressCount > 0) {
			toast.warning(t("delete_in_progress_warning", { count: inProgressCount }));
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
				toast.error(t("delete_conflict_error", { count: conflictCount }));
			} else {
				toast.error(t("delete_partial_failed"));
			}
			if (isSearchMode) {
				searchRemoveItems(deletableIds);
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
					searchRemoveItems([id]);
				}
				return true;
			} catch (e) {
				console.error("Error deleting document:", e);
				return false;
			}
		},
		[deleteDocumentMutation, isSearchMode, t, searchRemoveItems]
	);

	const sortKeyRef = useRef(sortKey);
	const sortDescRef = useRef(sortDesc);
	sortKeyRef.current = sortKey;
	sortDescRef.current = sortDesc;

	const handleSortChange = useCallback((key: SortKey) => {
		const currentKey = sortKeyRef.current;
		const currentDesc = sortDescRef.current;

		if (currentKey === key && currentDesc) {
			setSortKey("created_at");
			setSortDesc(true);
		} else if (currentKey === key) {
			setSortDesc(true);
		} else {
			setSortKey(key);
			setSortDesc(false);
		}
	}, []);

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
			<div className="shrink-0 p-4 pb-10">
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
					sortKey={sortKey}
					sortDesc={sortDesc}
					onSortChange={handleSortChange}
					deleteDocument={handleDeleteDocument}
					searchSpaceId={String(searchSpaceId)}
					hasMore={hasMore}
					loadingMore={loadingMore}
					onLoadMore={onLoadMore}
					isSearchMode={isSearchMode}
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
