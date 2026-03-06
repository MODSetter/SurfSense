"use client";

import { useAtom, useAtomValue } from "jotai";
import { ChevronLeft } from "lucide-react";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { sidebarSelectedDocumentsAtom } from "@/atoms/chat/mentioned-documents.atom";
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
	const { mutateAsync: deleteDocumentMutation } = useAtomValue(deleteDocumentMutationAtom);

	const [sidebarDocs, setSidebarDocs] = useAtom(sidebarSelectedDocumentsAtom);
	const mentionedDocIds = useMemo(() => new Set(sidebarDocs.map((d) => d.id)), [sidebarDocs]);

	const handleToggleChatMention = useCallback(
		(doc: { id: number; title: string; document_type: string }, isMentioned: boolean) => {
			if (isMentioned) {
				setSidebarDocs((prev) => prev.filter((d) => d.id !== doc.id));
			} else {
				setSidebarDocs((prev) => {
					if (prev.some((d) => d.id === doc.id)) return prev;
					return [
						...prev,
						{ id: doc.id, title: doc.title, document_type: doc.document_type as DocumentTypeEnum },
					];
				});
			}
		},
		[setSidebarDocs]
	);

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
	};

	const handleDeleteDocument = useCallback(
		async (id: number): Promise<boolean> => {
			try {
				await deleteDocumentMutation({ id });
				toast.success(t("delete_success") || "Document deleted");
				setSidebarDocs((prev) => prev.filter((d) => d.id !== id));
				if (isSearchMode) {
					searchRemoveItems([id]);
				}
				return true;
			} catch (e) {
				console.error("Error deleting document:", e);
				return false;
			}
		},
		[deleteDocumentMutation, isSearchMode, t, searchRemoveItems, setSidebarDocs]
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
						onSearch={setSearch}
						searchValue={search}
						onToggleType={onToggleType}
						activeTypes={activeTypes}
					/>
				</div>

				<DocumentsTableShell
					documents={displayDocs}
					loading={!!loading}
					error={!!error}
					sortKey={sortKey}
					sortDesc={sortDesc}
					onSortChange={handleSortChange}
					deleteDocument={handleDeleteDocument}
					searchSpaceId={String(searchSpaceId)}
					hasMore={hasMore}
					loadingMore={loadingMore}
					onLoadMore={onLoadMore}
					isSearchMode={isSearchMode}
					mentionedDocIds={mentionedDocIds}
					onToggleChatMention={handleToggleChatMention}
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
