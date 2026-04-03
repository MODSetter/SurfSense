"use client";

import { useQuery } from "@rocicorp/zero/react";
import { useAtom, useAtomValue, useSetAtom } from "jotai";
import { ChevronLeft, ChevronRight, Trash2, Unplug } from "lucide-react";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { DocumentsFilters } from "@/app/dashboard/[search_space_id]/documents/(manage)/components/DocumentsFilters";
import { sidebarSelectedDocumentsAtom } from "@/atoms/chat/mentioned-documents.atom";
import { connectorDialogOpenAtom } from "@/atoms/connector-dialog/connector-dialog.atoms";
import { connectorsAtom } from "@/atoms/connectors/connector-query.atoms";
import { deleteDocumentMutationAtom } from "@/atoms/documents/document-mutation.atoms";
import { expandedFolderIdsAtom } from "@/atoms/documents/folder.atoms";
import { agentCreatedDocumentsAtom } from "@/atoms/documents/ui.atoms";
import { openEditorPanelAtom } from "@/atoms/editor/editor-panel.atom";
import { rightPanelCollapsedAtom } from "@/atoms/layout/right-panel.atom";
import { CreateFolderDialog } from "@/components/documents/CreateFolderDialog";
import type { DocumentNodeDoc } from "@/components/documents/DocumentNode";
import type { FolderDisplay } from "@/components/documents/FolderNode";
import { FolderPickerDialog } from "@/components/documents/FolderPickerDialog";
import { FolderTreeView } from "@/components/documents/FolderTreeView";
import { VersionHistoryDialog } from "@/components/documents/version-history";
import { EXPORT_FILE_EXTENSIONS } from "@/components/shared/ExportMenuItems";
import {
	AlertDialog,
	AlertDialogAction,
	AlertDialogCancel,
	AlertDialogContent,
	AlertDialogDescription,
	AlertDialogFooter,
	AlertDialogHeader,
	AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Avatar, AvatarFallback, AvatarGroup } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";
import type { DocumentTypeEnum } from "@/contracts/types/document.types";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { useMediaQuery } from "@/hooks/use-media-query";
import { documentsApiService } from "@/lib/apis/documents-api.service";
import { foldersApiService } from "@/lib/apis/folders-api.service";
import { authenticatedFetch } from "@/lib/auth-utils";
import { queries } from "@/zero/queries/index";
import { SidebarSlideOutPanel } from "./SidebarSlideOutPanel";

const NON_DELETABLE_DOCUMENT_TYPES: readonly string[] = ["SURFSENSE_DOCS"];

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
	const setRightPanelCollapsed = useSetAtom(rightPanelCollapsedAtom);
	const openEditorPanel = useSetAtom(openEditorPanelAtom);
	const { data: connectors } = useAtomValue(connectorsAtom);
	const connectorCount = connectors?.length ?? 0;

	const [search, setSearch] = useState("");
	const debouncedSearch = useDebouncedValue(search, 250);
	const [activeTypes, setActiveTypes] = useState<DocumentTypeEnum[]>([]);
	const [watchedFolderIds, setWatchedFolderIds] = useState<Set<number>>(new Set());

	useEffect(() => {
		const api = typeof window !== "undefined" ? window.electronAPI : null;
		if (!api?.getWatchedFolders) return;

		async function loadWatchedIds() {
			const folders = await api!.getWatchedFolders();

			if (folders.length === 0) {
				try {
					const backendFolders = await documentsApiService.getWatchedFolders(searchSpaceId);
					for (const bf of backendFolders) {
						const meta = bf.metadata as Record<string, unknown> | null;
						if (!meta?.watched || !meta.folder_path) continue;
						await api!.addWatchedFolder({
							path: meta.folder_path as string,
							name: bf.name,
							rootFolderId: bf.id,
							searchSpaceId: bf.search_space_id,
							excludePatterns: (meta.exclude_patterns as string[]) ?? [],
							fileExtensions: (meta.file_extensions as string[] | null) ?? null,
							active: true,
						});
					}
					const recovered = await api!.getWatchedFolders();
					const ids = new Set(
						recovered.filter((f) => f.rootFolderId != null).map((f) => f.rootFolderId as number)
					);
					setWatchedFolderIds(ids);
					return;
				} catch (err) {
					console.error("[DocumentsSidebar] Recovery from backend failed:", err);
				}
			}

			const ids = new Set(
				folders.filter((f) => f.rootFolderId != null).map((f) => f.rootFolderId as number)
			);
			setWatchedFolderIds(ids);
		}

		loadWatchedIds();
	}, [searchSpaceId]);
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
	const [agentCreatedDocs, setAgentCreatedDocs] = useAtom(agentCreatedDocumentsAtom);

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

	const treeDocuments: DocumentNodeDoc[] = useMemo(() => {
		const zeroDocs = (zeroAllDocs ?? [])
			.filter((d) => {
				if (!d.title || d.title.trim() === "") return false;
				const state = (d.status as { state?: string } | undefined)?.state;
				if (state === "deleting") return false;
				return true;
			})
			.map((d) => ({
				id: d.id,
				title: d.title,
				document_type: d.documentType,
				folderId: (d as { folderId?: number | null }).folderId ?? null,
				status: d.status as { state: string; reason?: string | null } | undefined,
			}));

		const zeroIds = new Set(zeroDocs.map((d) => d.id));

		const pendingAgentDocs = agentCreatedDocs
			.filter((d) => d.searchSpaceId === searchSpaceId && !zeroIds.has(d.id))
			.map((d) => ({
				id: d.id,
				title: d.title,
				document_type: d.documentType,
				folderId: d.folderId ?? null,
				status: { state: "ready" } as { state: string; reason?: string | null },
			}));

		return [...pendingAgentDocs, ...zeroDocs];
	}, [zeroAllDocs, agentCreatedDocs, searchSpaceId]);

	// Prune agent-created docs once Zero has caught up
	useEffect(() => {
		if (!zeroAllDocs?.length || !agentCreatedDocs.length) return;
		const zeroIds = new Set(zeroAllDocs.map((d) => d.id));
		const remaining = agentCreatedDocs.filter((d) => !zeroIds.has(d.id));
		if (remaining.length < agentCreatedDocs.length) {
			setAgentCreatedDocs(remaining);
		}
	}, [zeroAllDocs, agentCreatedDocs, setAgentCreatedDocs]);

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

	const handleRescanFolder = useCallback(
		async (folder: FolderDisplay) => {
			const api = window.electronAPI;
			if (!api) return;

			const watchedFolders = await api.getWatchedFolders();
			const matched = watchedFolders.find((wf) => wf.rootFolderId === folder.id);
			if (!matched) {
				toast.error("This folder is not being watched");
				return;
			}

			try {
				await documentsApiService.folderIndex(searchSpaceId, {
					folder_path: matched.path,
					folder_name: matched.name,
					search_space_id: searchSpaceId,
					root_folder_id: folder.id,
				});
				toast.success(`Re-scanning folder: ${matched.name}`);
			} catch (err) {
				toast.error((err as Error)?.message || "Failed to re-scan folder");
			}
		},
		[searchSpaceId]
	);

	const handleStopWatching = useCallback(async (folder: FolderDisplay) => {
		const api = window.electronAPI;
		if (!api) return;

		const watchedFolders = await api.getWatchedFolders();
		const matched = watchedFolders.find((wf) => wf.rootFolderId === folder.id);
		if (!matched) {
			toast.error("This folder is not being watched");
			return;
		}

		await api.removeWatchedFolder(matched.path);
		try {
			await foldersApiService.stopWatching(folder.id);
		} catch (err) {
			console.error("[DocumentsSidebar] Failed to clear watched metadata:", err);
		}
		toast.success(`Stopped watching: ${matched.name}`);
	}, []);

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
			const api = window.electronAPI;
			if (api) {
				const watchedFolders = await api.getWatchedFolders();
				const matched = watchedFolders.find((wf) => wf.rootFolderId === folder.id);
				if (matched) {
					await api.removeWatchedFolder(matched.path);
				}
			}
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

	const handleExportDocument = useCallback(
		async (doc: DocumentNodeDoc, format: string) => {
			const safeTitle =
				doc.title
					.replace(/[^a-zA-Z0-9 _-]/g, "_")
					.trim()
					.slice(0, 80) || "document";
			const ext = EXPORT_FILE_EXTENSIONS[format] ?? format;

			try {
				const response = await authenticatedFetch(
					`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/search-spaces/${searchSpaceId}/documents/${doc.id}/export?format=${format}`,
					{ method: "GET" }
				);

				if (!response.ok) {
					const errorData = await response.json().catch(() => ({ detail: "Export failed" }));
					throw new Error(errorData.detail || "Export failed");
				}

				const blob = await response.blob();
				const url = URL.createObjectURL(blob);
				const a = document.createElement("a");
				a.href = url;
				a.download = `${safeTitle}.${ext}`;
				document.body.appendChild(a);
				a.click();
				document.body.removeChild(a);
				URL.revokeObjectURL(url);
			} catch (err) {
				console.error(`Export ${format} failed:`, err);
				toast.error(err instanceof Error ? err.message : `Export failed`);
			}
		},
		[searchSpaceId]
	);

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

	const handleToggleFolderSelect = useCallback(
		(folderId: number, selectAll: boolean) => {
			function collectSubtreeDocs(parentId: number): DocumentNodeDoc[] {
				const directDocs = (treeDocuments ?? []).filter(
					(d) =>
						d.folderId === parentId &&
						d.status?.state !== "pending" &&
						d.status?.state !== "processing"
				);
				const childFolders = foldersByParent[String(parentId)] ?? [];
				const descendantDocs = childFolders.flatMap((cf) => collectSubtreeDocs(cf.id));
				return [...directDocs, ...descendantDocs];
			}

			const subtreeDocs = collectSubtreeDocs(folderId);
			if (subtreeDocs.length === 0) return;

			if (selectAll) {
				setSidebarDocs((prev) => {
					const existingIds = new Set(prev.map((d) => d.id));
					const newDocs = subtreeDocs
						.filter((d) => !existingIds.has(d.id))
						.map((d) => ({
							id: d.id,
							title: d.title,
							document_type: d.document_type as DocumentTypeEnum,
						}));
					return newDocs.length > 0 ? [...prev, ...newDocs] : prev;
				});
			} else {
				const idsToRemove = new Set(subtreeDocs.map((d) => d.id));
				setSidebarDocs((prev) => prev.filter((d) => !idsToRemove.has(d.id)));
			}
		},
		[treeDocuments, foldersByParent, setSidebarDocs]
	);

	const searchFilteredDocuments = useMemo(() => {
		const query = debouncedSearch.trim().toLowerCase();
		if (!query) return treeDocuments;
		return treeDocuments.filter((d) => d.title.toLowerCase().includes(query));
	}, [treeDocuments, debouncedSearch]);

	const typeCounts = useMemo(() => {
		const counts: Partial<Record<string, number>> = {};
		for (const d of treeDocuments) {
			counts[d.document_type] = (counts[d.document_type] || 0) + 1;
		}
		return counts;
	}, [treeDocuments]);

	const deletableSelectedIds = useMemo(() => {
		const treeDocMap = new Map(treeDocuments.map((d) => [d.id, d]));
		return sidebarDocs
			.filter((doc) => {
				const fullDoc = treeDocMap.get(doc.id);
				if (!fullDoc) return false;
				const state = fullDoc.status?.state ?? "ready";
				return (
					state !== "pending" &&
					state !== "processing" &&
					!NON_DELETABLE_DOCUMENT_TYPES.includes(doc.document_type)
				);
			})
			.map((doc) => doc.id);
	}, [sidebarDocs, treeDocuments]);

	const [bulkDeleteConfirmOpen, setBulkDeleteConfirmOpen] = useState(false);
	const [isBulkDeleting, setIsBulkDeleting] = useState(false);
	const [versionDocId, setVersionDocId] = useState<number | null>(null);

	const handleBulkDeleteSelected = useCallback(async () => {
		if (deletableSelectedIds.length === 0) return;
		setIsBulkDeleting(true);
		try {
			const results = await Promise.allSettled(
				deletableSelectedIds.map(async (id) => {
					await deleteDocumentMutation({ id });
					return id;
				})
			);
			const successIds = results
				.filter((r): r is PromiseFulfilledResult<number> => r.status === "fulfilled")
				.map((r) => r.value);
			const failed = results.length - successIds.length;
			if (successIds.length > 0) {
				setSidebarDocs((prev) => {
					const idSet = new Set(successIds);
					return prev.filter((d) => !idSet.has(d.id));
				});
				toast.success(`Deleted ${successIds.length} document${successIds.length !== 1 ? "s" : ""}`);
			}
			if (failed > 0) {
				toast.error(`Failed to delete ${failed} document${failed !== 1 ? "s" : ""}`);
			}
		} catch {
			toast.error("Failed to delete documents");
		}
		setIsBulkDeleting(false);
		setBulkDeleteConfirmOpen(false);
	}, [deletableSelectedIds, deleteDocumentMutation, setSidebarDocs]);

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
				return true;
			} catch (e) {
				console.error("Error deleting document:", e);
				return false;
			}
		},
		[deleteDocumentMutation, t, setSidebarDocs]
	);

	useEffect(() => {
		const handleEscape = (e: KeyboardEvent) => {
			if (e.key === "Escape" && open) {
				if (isMobile) {
					onOpenChange(false);
				} else {
					setRightPanelCollapsed(true);
				}
			}
		};
		document.addEventListener("keydown", handleEscape);
		return () => document.removeEventListener("keydown", handleEscape);
	}, [open, onOpenChange, isMobile, setRightPanelCollapsed]);

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
			<div className="shrink-0 mx-4 mt-4 mb-4 flex select-none items-center gap-2 rounded-lg border bg-muted/50 transition-colors hover:bg-muted/80">
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
						typeCounts={typeCounts}
						onSearch={setSearch}
						searchValue={search}
						onToggleType={onToggleType}
						activeTypes={activeTypes}
						onCreateFolder={() => handleCreateFolder(null)}
					/>
				</div>

				<div className="relative flex-1 min-h-0 overflow-auto">
					{deletableSelectedIds.length > 0 && (
						<div className="absolute inset-x-0 top-0 z-10 flex items-center justify-center px-4 py-1.5 animate-in fade-in duration-150 pointer-events-none">
							<button
								type="button"
								onClick={() => setBulkDeleteConfirmOpen(true)}
								className="pointer-events-auto flex items-center gap-1.5 px-3 py-1 rounded-md bg-destructive text-destructive-foreground shadow-lg text-xs font-medium hover:bg-destructive/90 transition-colors"
							>
								<Trash2 size={12} />
								Delete {deletableSelectedIds.length}{" "}
								{deletableSelectedIds.length === 1 ? "item" : "items"}
							</button>
						</div>
					)}

					<FolderTreeView
						folders={treeFolders}
						documents={searchFilteredDocuments}
						expandedIds={expandedIds}
						onToggleExpand={toggleFolderExpand}
						mentionedDocIds={mentionedDocIds}
						onToggleChatMention={handleToggleChatMention}
						onToggleFolderSelect={handleToggleFolderSelect}
						onRenameFolder={handleRenameFolder}
						onDeleteFolder={handleDeleteFolder}
						onMoveFolder={handleMoveFolder}
						onCreateFolder={handleCreateFolder}
						searchQuery={debouncedSearch.trim() || undefined}
						onPreviewDocument={(doc) => {
							openEditorPanel({
								documentId: doc.id,
								searchSpaceId,
								title: doc.title,
							});
						}}
						onEditDocument={(doc) => {
							openEditorPanel({
								documentId: doc.id,
								searchSpaceId,
								title: doc.title,
							});
						}}
						onDeleteDocument={(doc) => handleDeleteDocument(doc.id)}
						onMoveDocument={handleMoveDocument}
						onExportDocument={handleExportDocument}
						onVersionHistory={(doc) => setVersionDocId(doc.id)}
						activeTypes={activeTypes}
						onDropIntoFolder={handleDropIntoFolder}
						onReorderFolder={handleReorderFolder}
						watchedFolderIds={watchedFolderIds}
						onRescanFolder={handleRescanFolder}
						onStopWatchingFolder={handleStopWatching}
					/>
				</div>
			</div>

			{versionDocId !== null && (
				<VersionHistoryDialog
					open
					onOpenChange={(open) => {
						if (!open) setVersionDocId(null);
					}}
					documentId={versionDocId}
				/>
			)}

			<FolderPickerDialog
				open={folderPickerOpen}
				onOpenChange={setFolderPickerOpen}
				folders={treeFolders}
				title={folderPickerTarget?.type === "folder" ? "Move folder to" : "Move document to"}
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

			<AlertDialog
				open={bulkDeleteConfirmOpen}
				onOpenChange={(open) => !open && !isBulkDeleting && setBulkDeleteConfirmOpen(false)}
			>
				<AlertDialogContent>
					<AlertDialogHeader>
						<AlertDialogTitle>
							Delete {deletableSelectedIds.length} document
							{deletableSelectedIds.length !== 1 ? "s" : ""}?
						</AlertDialogTitle>
						<AlertDialogDescription>
							This action cannot be undone.{" "}
							{deletableSelectedIds.length === 1
								? "This document"
								: `These ${deletableSelectedIds.length} documents`}{" "}
							will be permanently deleted from your search space.
						</AlertDialogDescription>
					</AlertDialogHeader>
					<AlertDialogFooter>
						<AlertDialogCancel disabled={isBulkDeleting}>Cancel</AlertDialogCancel>
						<AlertDialogAction
							onClick={(e) => {
								e.preventDefault();
								handleBulkDeleteSelected();
							}}
							disabled={isBulkDeleting}
							className="relative bg-destructive text-destructive-foreground hover:bg-destructive/90"
						>
							<span className={isBulkDeleting ? "opacity-0" : ""}>Delete</span>
							{isBulkDeleting && <Spinner size="sm" className="absolute" />}
						</AlertDialogAction>
					</AlertDialogFooter>
				</AlertDialogContent>
			</AlertDialog>
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
