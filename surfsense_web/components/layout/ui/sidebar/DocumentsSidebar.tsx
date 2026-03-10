"use client";

import { useAtom, useAtomValue, useSetAtom } from "jotai";
import { ChevronLeft, ChevronRight, Unplug } from "lucide-react";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { DocumentsFilters } from "@/app/dashboard/[search_space_id]/documents/(manage)/components/DocumentsFilters";
import {
	DocumentsTableShell,
	type SortKey,
} from "@/app/dashboard/[search_space_id]/documents/(manage)/components/DocumentsTableShell";
import { sidebarSelectedDocumentsAtom } from "@/atoms/chat/mentioned-documents.atom";
import { connectorDialogOpenAtom } from "@/atoms/connector-dialog/connector-dialog.atoms";
import { deleteDocumentMutationAtom } from "@/atoms/documents/document-mutation.atoms";
import { Avatar, AvatarFallback, AvatarGroup } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";
import type { DocumentTypeEnum } from "@/contracts/types/document.types";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { useDocumentSearch } from "@/hooks/use-document-search";
import { useDocuments } from "@/hooks/use-documents";
import { useMediaQuery } from "@/hooks/use-media-query";
import { SidebarSlideOutPanel } from "./SidebarSlideOutPanel";

const SHOWCASE_CONNECTORS = [
	{ type: "GOOGLE_DRIVE_CONNECTOR", label: "Google Drive" },
	{ type: "GOOGLE_GMAIL_CONNECTOR", label: "Gmail" },
	{ type: "NOTION_CONNECTOR", label: "Notion" },
	{ type: "YOUTUBE_CONNECTOR", label: "YouTube" },
	{ type: "GOOGLE_CALENDAR_CONNECTOR", label: "Google Calendar" },
	{ type: "SLACK_CONNECTOR", label: "Slack" },
	{ type: "LINEAR_CONNECTOR", label: "Linear" },
	{ type: "JIRA_CONNECTOR", label: "Jira" },
	{ type: "GITHUB_CONNECTOR", label: "GitHub" },
] as const;

interface DocumentsSidebarProps {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	isDocked?: boolean;
	onDockedChange?: (docked: boolean) => void;
	/** When true, renders content without any wrapper — parent provides the container */
	embedded?: boolean;
	/** Optional action element rendered in the header row (e.g. collapse button) */
	headerAction?: React.ReactNode;
}

export function DocumentsSidebar({
	open,
	onOpenChange,
	isDocked = false,
	onDockedChange,
	embedded = false,
	headerAction,
}: DocumentsSidebarProps) {
	const t = useTranslations("documents");
	const tSidebar = useTranslations("sidebar");
	const params = useParams();
	const isMobile = !useMediaQuery("(min-width: 640px)");
	const searchSpaceId = Number(params.search_space_id);
	const setConnectorDialogOpen = useSetAtom(connectorDialogOpenAtom);

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
			<div className="shrink-0 flex h-14 items-center px-4">
				<div className="flex w-full items-center justify-between">
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
						<h2 className="select-none text-lg font-semibold">{t("title") || "Documents"}</h2>
					</div>
					<div className="flex items-center gap-1">
						{!isMobile && onDockedChange && (
							<Tooltip>
								<TooltipTrigger asChild>
									<Button
										variant="ghost"
										size="icon"
										className="h-8 w-8 rounded-full"
										onClick={() => {
											if (isDocked) {
												onDockedChange(false);
												onOpenChange(false);
											} else {
												onDockedChange(true);
											}
										}}
									>
										{isDocked ? (
											<ChevronLeft className="h-4 w-4 text-muted-foreground" />
										) : (
											<ChevronRight className="h-4 w-4 text-muted-foreground" />
										)}
										<span className="sr-only">{isDocked ? "Collapse panel" : "Expand panel"}</span>
									</Button>
								</TooltipTrigger>
								<TooltipContent className="z-80">
									{isDocked ? "Collapse panel" : "Expand panel"}
								</TooltipContent>
							</Tooltip>
						)}
						{headerAction}
					</div>
				</div>
			</div>

			{/* Connected tools strip */}
			<div className="shrink-0 mx-4 mt-2 mb-3 flex select-none items-center gap-2 rounded-lg border bg-muted/50 px-3 py-2">
				<button
					type="button"
					onClick={() => setConnectorDialogOpen(true)}
					className="flex items-center gap-2 min-w-0 flex-1 text-left"
				>
					<Unplug className="size-4 shrink-0 text-muted-foreground" />
					<span className="truncate text-xs text-muted-foreground">Connect your tools</span>
					<AvatarGroup className="ml-auto shrink-0">
						{SHOWCASE_CONNECTORS.map(({ type, label }, i) => (
							<Tooltip key={type}>
								<TooltipTrigger asChild>
									<Avatar className="size-6" style={{ zIndex: SHOWCASE_CONNECTORS.length - i }}>
										<AvatarFallback className="bg-muted text-[10px]">
											{getConnectorIcon(type, "size-3.5")}
										</AvatarFallback>
									</Avatar>
								</TooltipTrigger>
								<TooltipContent side="top" className="text-xs">
									{label}
								</TooltipContent>
							</Tooltip>
						))}
					</AvatarGroup>
				</button>
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
					mentionedDocIds={mentionedDocIds}
					onToggleChatMention={handleToggleChatMention}
					onEditNavigate={() => onOpenChange(false)}
					isSearchMode={isSearchMode || activeTypes.length > 0}
				/>
			</div>
		</>
	);

	if (embedded) {
		return (
			<div className="flex h-full flex-col bg-sidebar text-sidebar-foreground">
				{documentsContent}
			</div>
		);
	}

	if (isDocked && open && !isMobile) {
		return (
			<aside
				className="h-full w-[380px] shrink-0 bg-sidebar text-sidebar-foreground flex flex-col border-r"
				aria-label={t("title") || "Documents"}
			>
				{documentsContent}
			</aside>
		);
	}

	return (
		<SidebarSlideOutPanel
			open={open}
			onOpenChange={onOpenChange}
			ariaLabel={t("title") || "Documents"}
			width={isMobile ? undefined : 380}
		>
			{documentsContent}
		</SidebarSlideOutPanel>
	);
}
