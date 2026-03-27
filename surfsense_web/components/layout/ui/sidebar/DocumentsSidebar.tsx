"use client";

import { useQuery } from "@rocicorp/zero/react";
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
import { connectorsAtom } from "@/atoms/connectors/connector-query.atoms";
import { deleteDocumentMutationAtom } from "@/atoms/documents/document-mutation.atoms";
import { expandedFolderIdsAtom } from "@/atoms/documents/folder.atoms";
import { openDocumentTabAtom } from "@/atoms/tabs/tabs.atom";
import { CreateFolderDialog } from "@/components/documents/CreateFolderDialog";
import type { DocumentNodeDoc } from "@/components/documents/DocumentNode";
import type { FolderDisplay } from "@/components/documents/FolderNode";
import { FolderPickerDialog } from "@/components/documents/FolderPickerDialog";
import { FolderTreeView } from "@/components/documents/FolderTreeView";
import { Avatar, AvatarFallback, AvatarGroup } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";
import type { DocumentTypeEnum } from "@/contracts/types/document.types";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { useDocumentSearch } from "@/hooks/use-document-search";
import { useDocuments } from "@/hooks/use-documents";
import { useMediaQuery } from "@/hooks/use-media-query";
import { foldersApiService } from "@/lib/apis/folders-api.service";
import { queries } from "@/zero/queries/index";
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
	const openDocumentTab = useSetAtom(openDocumentTabAtom);
	const { data: connectors } = useAtomValue(connectorsAtom);
	const connectorCount = connectors?.length ?? 0;

	const [search, setSearch] = useState("");
	const debouncedSearch = useDebouncedValue(search, 250);
	const [activeTypes, setActiveTypes] = useState<DocumentTypeEnum[]>([]);
	const [sortKey, setSortKey] = useState<SortKey>("created_at");
	const [sortDesc, setSortDesc] = useState(true);
	const { mutateAsync: deleteDocumentMutation } = useAtomValue(deleteDocumentMutationAtom);

	const [sidebarDocs, setSidebarDocs] = useAtom(sidebarSelectedDocumentsAtom);
	const mentionedDocIds = useMemo(() => new Set(sidebarDocs.map((d) => d.id)), [sidebarDocs]);

	// Folder state
	const [expandedFolderMap, setExpandedFolderMap] = useAtom(expandedFolderIdsAtom);
	const expandedIds = useMemo(
		() => new Set(expandedFolderMap[searchSpaceId] ?? []),
		[expandedFolderMap, searchSpaceId]
	);
	const toggleFolderExpand = useCallback(
		(folderId: number) => {
			setExpandedFolderMap((prev) => {
				const current = new Set(prev[searchSpaceId] ?? []);
				if (current.has(folderId)) current.delete(folderId);
				else current.add(folderId);
				return { ...prev, [searchSpaceId]: [...current] };
			});
		},
		[searchSpaceId, setExpandedFolderMap]
	);

	// Zero queries for tree data
	const [zeroFolders] = useQuery(queries.folders.bySpace({ searchSpaceId }));
	const [zeroAllDocs] = useQuery(queries.documents.bySpace({ searchSpaceId }));

	const treeFolders: FolderDisplay[] = useMemo(
		() =>
			(zeroFolders ?? []).map((f) => ({
				id: f.id,
				name: f.name,
				position: f.position,
				parentId: f.parentId ?? null,
				searchSpaceId: f.searchSpaceId,
			})),
		[zeroFolders]
	);

	const treeDocuments: DocumentNodeDoc[] = useMemo(
		() =>
			(zeroAllDocs ?? [])
				.filter((d) => d.title && d.title.trim() !== "")
				.map((d) => ({
					id: d.id,
					title: d.title,
					document_type: d.documentType,
					folderId: (d as { folderId?: number | null }).folderId ?? null,
					status: d.status as { state: string; reason?: string | null } | undefined,
				})),
		[zeroAllDocs]
	);

	const foldersByParent = useMemo(() => {
		const map: Record<string, FolderDisplay[]> = {};
		for (const f of treeFolders) {
			const key = String(f.parentId ?? "root");
			if (!map[key]) map[key] = [];
			map[key].push(f);
		}
		return map;
	}, [treeFolders]);

	// Folder actions
	const [folderPickerOpen, setFolderPickerOpen] = useState(false);
	const [folderPickerTarget, setFolderPickerTarget] = useState<{
		type: "folder" | "document";
		id: number;
		disabledIds?: Set<number>;
	} | null>(null);

	// Create-folder dialog state
	const [createFolderOpen, setCreateFolderOpen] = useState(false);
	const [createFolderParentId, setCreateFolderParentId] = useState<number | null>(null);

	const createFolderParentName = useMemo(() => {
		if (createFolderParentId === null) return null;
		return treeFolders.find((f) => f.id === createFolderParentId)?.name ?? null;
	}, [createFolderParentId, treeFolders]);

	const handleCreateFolder = useCallback((parentId: number | null) => {
		setCreateFolderParentId(parentId);
		setCreateFolderOpen(true);
	}, []);

	const handleCreateFolderConfirm = useCallback(
		async (name: string) => {
			try {
				await foldersApiService.createFolder({
					name,
					parent_id: createFolderParentId,
					search_space_id: searchSpaceId,
				});
				toast.success("Folder created");
				if (createFolderParentId !== null) {
					setExpandedFolderMap((prev) => {
						const current = new Set(prev[searchSpaceId] ?? []);
						current.add(createFolderParentId);
						return { ...prev, [searchSpaceId]: [...current] };
					});
				}
			} catch (e: unknown) {
				toast.error((e as Error)?.message || "Failed to create folder");
			}
		},
		[createFolderParentId, searchSpaceId, setExpandedFolderMap]
	);

	const handleRenameFolder = useCallback(async (folder: FolderDisplay, newName: string) => {
		try {
			await foldersApiService.updateFolder(folder.id, { name: newName });
			toast.success("Folder renamed");
		} catch (e: unknown) {
			toast.error((e as Error)?.message || "Failed to rename folder");
		}
	}, []);

	const handleDeleteFolder = useCallback(async (folder: FolderDisplay) => {
		if (!confirm(`Delete folder "${folder.name}" and all its contents?`)) return;
		try {
			await foldersApiService.deleteFolder(folder.id);
			toast.success("Folder deleted");
		} catch (e: unknown) {
			toast.error((e as Error)?.message || "Failed to delete folder");
		}
	}, []);

	const handleMoveFolder = useCallback(
		(folder: FolderDisplay) => {
			const subtreeIds = new Set<number>();
			function collectSubtree(id: number) {
				subtreeIds.add(id);
				for (const child of foldersByParent[String(id)] ?? []) {
					collectSubtree(child.id);
				}
			}
			collectSubtree(folder.id);
			setFolderPickerTarget({
				type: "folder",
				id: folder.id,
				disabledIds: subtreeIds,
			});
			setFolderPickerOpen(true);
		},
		[foldersByParent]
	);

	const handleMoveDocument = useCallback((doc: DocumentNodeDoc) => {
		setFolderPickerTarget({ type: "document", id: doc.id });
		setFolderPickerOpen(true);
	}, []);

	const handleFolderPickerSelect = useCallback(
		async (targetFolderId: number | null) => {
			if (!folderPickerTarget) return;
			try {
				if (folderPickerTarget.type === "folder") {
					await foldersApiService.moveFolder(folderPickerTarget.id, {
						new_parent_id: targetFolderId,
					});
					toast.success("Folder moved");
				} else {
					await foldersApiService.moveDocument(folderPickerTarget.id, {
						folder_id: targetFolderId,
					});
					toast.success("Document moved");
				}
			} catch (e: unknown) {
				toast.error((e as Error)?.message || "Failed to move item");
			}
			setFolderPickerTarget(null);
		},
		[folderPickerTarget]
	);

	const handleDropIntoFolder = useCallback(
		async (itemType: "folder" | "document", itemId: number, targetFolderId: number | null) => {
			try {
				if (itemType === "folder") {
					await foldersApiService.moveFolder(itemId, {
						new_parent_id: targetFolderId,
					});
					toast.success("Folder moved");
				} else {
					await foldersApiService.moveDocument(itemId, {
						folder_id: targetFolderId,
					});
					toast.success("Document moved");
				}
			} catch (e: unknown) {
				toast.error((e as Error)?.message || "Failed to move item");
			}
		},
		[]
	);

	const handleReorderFolder = useCallback(
		async (folderId: number, beforePos: string | null, afterPos: string | null) => {
			try {
				await foldersApiService.reorderFolder(folderId, {
					before_position: beforePos,
					after_position: afterPos,
				});
			} catch (e: unknown) {
				toast.error((e as Error)?.message || "Failed to reorder folder");
			}
		},
		[]
	);

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
		removeItems: realtimeRemoveItems,
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

	const onToggleType = useCallback((type: DocumentTypeEnum, checked: boolean) => {
		setActiveTypes((prev) => {
			if (checked) {
				return prev.includes(type) ? prev : [...prev, type];
			}
			return prev.filter((t) => t !== type);
		});
	}, []);

	const handleDeleteDocument = useCallback(
		async (id: number): Promise<boolean> => {
			try {
				await deleteDocumentMutation({ id });
				toast.success(t("delete_success") || "Document deleted");
				setSidebarDocs((prev) => prev.filter((d) => d.id !== id));
				realtimeRemoveItems([id]);
				if (isSearchMode) {
					searchRemoveItems([id]);
				}
				return true;
			} catch (e) {
				console.error("Error deleting document:", e);
				return false;
			}
		},
		[
			deleteDocumentMutation,
			isSearchMode,
			t,
			searchRemoveItems,
			realtimeRemoveItems,
			setSidebarDocs,
		]
	);

	const handleBulkDeleteDocuments = useCallback(
		async (ids: number[]): Promise<{ success: number; failed: number }> => {
			const successIds: number[] = [];
			const results = await Promise.allSettled(
				ids.map(async (id) => {
					await deleteDocumentMutation({ id });
					successIds.push(id);
				})
			);
			if (successIds.length > 0) {
				setSidebarDocs((prev) => prev.filter((d) => !successIds.includes(d.id)));
				realtimeRemoveItems(successIds);
				if (isSearchMode) {
					searchRemoveItems(successIds);
				}
			}
			const success = results.filter((r) => r.status === "fulfilled").length;
			const failed = results.filter((r) => r.status === "rejected").length;
			return { success, failed };
		},
		[deleteDocumentMutation, isSearchMode, searchRemoveItems, realtimeRemoveItems, setSidebarDocs]
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
			<div className="shrink-0 mx-4 mt-2 mb-3 flex select-none items-center gap-2 rounded-lg border bg-muted/50 transition-colors hover:bg-muted/80">
				<button
					type="button"
					onClick={() => setConnectorDialogOpen(true)}
					className="flex items-center gap-2 min-w-0 flex-1 text-left px-3 py-2"
				>
					<Unplug className="size-4 shrink-0 text-muted-foreground" />
					<span className="truncate text-xs text-muted-foreground">
						{connectorCount > 0 ? "Manage connectors" : "Connect your connectors"}
					</span>
					{connectorCount > 0 && (
						<span className="shrink-0 rounded-full bg-muted-foreground/15 px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
							{connectorCount}
						</span>
					)}
					<AvatarGroup className="ml-auto shrink-0">
						{connectorCount > 0 && connectors
							? connectors.slice(0, isMobile ? 5 : 9).map((connector, i) => {
									const avatar = (
										<Avatar
											key={connector.id}
											className="size-6"
											style={{ zIndex: Math.max(9 - i, 1) }}
										>
											<AvatarFallback className="bg-muted text-[10px]">
												{getConnectorIcon(connector.connector_type, "size-3.5")}
											</AvatarFallback>
										</Avatar>
									);
									if (isMobile) return avatar;
									return (
										<Tooltip key={connector.id}>
											<TooltipTrigger asChild>{avatar}</TooltipTrigger>
											<TooltipContent side="top" className="text-xs">
												{connector.name}
											</TooltipContent>
										</Tooltip>
									);
								})
							: (isMobile ? SHOWCASE_CONNECTORS.slice(0, 5) : SHOWCASE_CONNECTORS).map(
									({ type, label }, i) => {
										const avatar = (
											<Avatar
												key={type}
												className="size-6"
												style={{ zIndex: SHOWCASE_CONNECTORS.length - i }}
											>
												<AvatarFallback className="bg-muted text-[10px]">
													{getConnectorIcon(type, "size-3.5")}
												</AvatarFallback>
											</Avatar>
										);
										if (isMobile) return avatar;
										return (
											<Tooltip key={type}>
												<TooltipTrigger asChild>{avatar}</TooltipTrigger>
												<TooltipContent side="top" className="text-xs">
													{label}
												</TooltipContent>
											</Tooltip>
										);
									}
								)}
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
						onCreateFolder={() => handleCreateFolder(null)}
					/>
				</div>

				{isSearchMode ? (
					<DocumentsTableShell
						documents={displayDocs}
						loading={!!loading}
						error={!!error}
						sortKey={sortKey}
						sortDesc={sortDesc}
						onSortChange={handleSortChange}
						deleteDocument={handleDeleteDocument}
						bulkDeleteDocuments={handleBulkDeleteDocuments}
						searchSpaceId={String(searchSpaceId)}
						hasMore={hasMore}
						loadingMore={loadingMore}
						onLoadMore={onLoadMore}
						mentionedDocIds={mentionedDocIds}
						onToggleChatMention={handleToggleChatMention}
						isSearchMode={isSearchMode || activeTypes.length > 0}
					/>
				) : (
					<FolderTreeView
						folders={treeFolders}
						documents={treeDocuments}
						expandedIds={expandedIds}
						onToggleExpand={toggleFolderExpand}
						mentionedDocIds={mentionedDocIds}
						onToggleChatMention={handleToggleChatMention}
						onRenameFolder={handleRenameFolder}
						onDeleteFolder={handleDeleteFolder}
						onMoveFolder={handleMoveFolder}
						onCreateFolder={handleCreateFolder}
						onPreviewDocument={(doc) => {
							openDocumentTab({
								documentId: doc.id,
								searchSpaceId,
								title: doc.title,
							});
						}}
						onEditDocument={(doc) => {
							openDocumentTab({
								documentId: doc.id,
								searchSpaceId,
								title: doc.title,
							});
						}}
						onDeleteDocument={(doc) => handleDeleteDocument(doc.id)}
						onMoveDocument={handleMoveDocument}
						activeTypes={activeTypes}
						onDropIntoFolder={handleDropIntoFolder}
						onReorderFolder={handleReorderFolder}
					/>
				)}
			</div>

			<FolderPickerDialog
				open={folderPickerOpen}
				onOpenChange={setFolderPickerOpen}
				folders={treeFolders}
				title={folderPickerTarget?.type === "folder" ? "Move folder to..." : "Move document to..."}
				description="Select a destination folder, or choose Root to move to the top level."
				disabledFolderIds={folderPickerTarget?.disabledIds}
				onSelect={handleFolderPickerSelect}
			/>

			<CreateFolderDialog
				open={createFolderOpen}
				onOpenChange={setCreateFolderOpen}
				parentFolderName={createFolderParentName}
				onConfirm={handleCreateFolderConfirm}
			/>
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
