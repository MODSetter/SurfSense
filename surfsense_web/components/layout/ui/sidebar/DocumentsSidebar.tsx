"use client";

import { useQuery } from "@rocicorp/zero/react";
import { useAtom, useAtomValue, useSetAtom } from "jotai";
import {
	ChevronLeft,
	ChevronRight,
	FileText,
	Folder,
	FolderPlus,
	FolderClock,
	Laptop,
	Lock,
	Paperclip,
	Search,
	Server,
	Trash2,
	Unplug,
	Upload,
	X,
} from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import type React from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { sidebarSelectedDocumentsAtom } from "@/atoms/chat/mentioned-documents.atom";
import { connectorDialogOpenAtom } from "@/atoms/connector-dialog/connector-dialog.atoms";
import { connectorsAtom } from "@/atoms/connectors/connector-query.atoms";
import { deleteDocumentMutationAtom } from "@/atoms/documents/document-mutation.atoms";
import { expandedFolderIdsAtom } from "@/atoms/documents/folder.atoms";
import { agentCreatedDocumentsAtom } from "@/atoms/documents/ui.atoms";
import { openEditorPanelAtom } from "@/atoms/editor/editor-panel.atom";
import {
	folderWatchDialogOpenAtom,
	folderWatchInitialFolderAtom,
} from "@/atoms/folder-sync/folder-sync.atoms";
import { rightPanelCollapsedAtom } from "@/atoms/layout/right-panel.atom";
import { searchSpacesAtom } from "@/atoms/search-spaces/search-space-query.atoms";
import { CreateFolderDialog } from "@/components/documents/CreateFolderDialog";
import type { DocumentNodeDoc } from "@/components/documents/DocumentNode";
import { DocumentsFilters } from "@/components/documents/DocumentsFilters";
import type { FolderDisplay } from "@/components/documents/FolderNode";
import { FolderPickerDialog } from "@/components/documents/FolderPickerDialog";
import { FolderTreeView } from "@/components/documents/FolderTreeView";
import { VersionHistoryDialog } from "@/components/documents/version-history";
import { EXPORT_FILE_EXTENSIONS } from "@/components/shared/ExportMenuItems";
import {
	DEFAULT_EXCLUDE_PATTERNS,
	FolderWatchDialog,
	type SelectedFolder,
} from "@/components/sources/FolderWatchDialog";
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
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuLabel,
	DropdownMenuSeparator,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Drawer, DrawerContent, DrawerHandle, DrawerTitle } from "@/components/ui/drawer";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import { Spinner } from "@/components/ui/spinner";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useAnonymousMode, useIsAnonymous } from "@/contexts/anonymous-mode";
import { useLoginGate } from "@/contexts/login-gate";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";
import type { DocumentTypeEnum } from "@/contracts/types/document.types";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { useMediaQuery } from "@/hooks/use-media-query";
import { useElectronAPI } from "@/hooks/use-platform";
import { anonymousChatApiService } from "@/lib/apis/anonymous-chat-api.service";
import { documentsApiService } from "@/lib/apis/documents-api.service";
import { foldersApiService } from "@/lib/apis/folders-api.service";
import { searchSpacesApiService } from "@/lib/apis/search-spaces-api.service";
import { authenticatedFetch } from "@/lib/auth-utils";
import { uploadFolderScan } from "@/lib/folder-sync-upload";
import { getSupportedExtensionsSet } from "@/lib/supported-extensions";
import { queries } from "@/zero/queries/index";
import { LocalFilesystemBrowser } from "./LocalFilesystemBrowser";
import { SidebarSlideOutPanel } from "./SidebarSlideOutPanel";

const NON_DELETABLE_DOCUMENT_TYPES: readonly string[] = ["SURFSENSE_DOCS"];
const LOCAL_FILESYSTEM_TRUST_KEY = "surfsense.local-filesystem-trust.v1";
const MAX_LOCAL_FILESYSTEM_ROOTS = 10;

function CloudDocumentsSkeleton() {
	const rows = [
		{ id: "row-1", widthClass: "w-44" },
		{ id: "row-2", widthClass: "w-32" },
		{ id: "row-3", widthClass: "w-32" },
		{ id: "row-4", widthClass: "w-44" },
		{ id: "row-5", widthClass: "w-32" },
		{ id: "row-6", widthClass: "w-32" },
		{ id: "row-7", widthClass: "w-44" },
		{ id: "row-8", widthClass: "w-32" },
	];

	return (
		<div className="flex-1 min-h-0 overflow-y-auto px-2 py-1">
			<div className="space-y-1">
				{rows.map((row) => (
					<div key={row.id} className="flex h-8 items-center gap-2 px-2">
						<Skeleton className="h-4 w-4 rounded-sm" />
						<Skeleton className={`h-4 ${row.widthClass}`} />
					</div>
				))}
			</div>
		</div>
	);
}

type FilesystemSettings = {
	mode: "cloud" | "desktop_local_folder";
	localRootPaths: string[];
	updatedAt: string;
};

interface WatchedFolderEntry {
	path: string;
	name: string;
	excludePatterns: string[];
	fileExtensions: string[] | null;
	rootFolderId: number | null;
	searchSpaceId: number;
	active: boolean;
}

const getFolderDisplayName = (rootPath: string): string =>
	rootPath.split(/[\\/]/).at(-1) || rootPath;

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

export function DocumentsSidebar(props: DocumentsSidebarProps) {
	const isAnonymous = useIsAnonymous();
	if (isAnonymous) {
		return <AnonymousDocumentsSidebar {...props} />;
	}
	return <AuthenticatedDocumentsSidebar {...props} />;
}

function AuthenticatedDocumentsSidebar({
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
	const electronAPI = useElectronAPI();
	const searchSpaceId = Number(params.search_space_id);
	const setConnectorDialogOpen = useSetAtom(connectorDialogOpenAtom);
	const setRightPanelCollapsed = useSetAtom(rightPanelCollapsedAtom);
	const openEditorPanel = useSetAtom(openEditorPanelAtom);
	const { data: connectors } = useAtomValue(connectorsAtom);
	const connectorCount = connectors?.length ?? 0;

	const [search, setSearch] = useState("");
	const debouncedSearch = useDebouncedValue(search, 250);
	const [localSearch, setLocalSearch] = useState("");
	const debouncedLocalSearch = useDebouncedValue(localSearch, 250);
	const localSearchInputRef = useRef<HTMLInputElement>(null);
	const [activeTypes, setActiveTypes] = useState<DocumentTypeEnum[]>([]);
	const [filesystemSettings, setFilesystemSettings] = useState<FilesystemSettings | null>(null);
	const [localTrustDialogOpen, setLocalTrustDialogOpen] = useState(false);
	const [pendingLocalPath, setPendingLocalPath] = useState<string | null>(null);
	const [watchedFolderIds, setWatchedFolderIds] = useState<Set<number>>(new Set());
	const [folderWatchOpen, setFolderWatchOpen] = useAtom(folderWatchDialogOpenAtom);
	const [watchInitialFolder, setWatchInitialFolder] = useAtom(folderWatchInitialFolderAtom);
	const isElectron = typeof window !== "undefined" && !!window.electronAPI;

	useEffect(() => {
		if (!electronAPI?.getAgentFilesystemSettings) return;
		let mounted = true;
		electronAPI
			.getAgentFilesystemSettings()
			.then((settings: FilesystemSettings) => {
				if (!mounted) return;
				setFilesystemSettings(settings);
			})
			.catch(() => {
				if (!mounted) return;
				setFilesystemSettings({
					mode: "cloud",
					localRootPaths: [],
					updatedAt: new Date().toISOString(),
				});
			});
		return () => {
			mounted = false;
		};
	}, [electronAPI]);

	const hasLocalFilesystemTrust = useCallback(() => {
		try {
			return window.localStorage.getItem(LOCAL_FILESYSTEM_TRUST_KEY) === "true";
		} catch {
			return false;
		}
	}, []);

	const localRootPaths = filesystemSettings?.localRootPaths ?? [];
	const canAddMoreLocalRoots = localRootPaths.length < MAX_LOCAL_FILESYSTEM_ROOTS;

	const applyLocalRootPath = useCallback(
		async (path: string) => {
			if (!electronAPI?.setAgentFilesystemSettings) return;
			const nextLocalRootPaths = [path, ...localRootPaths]
				.filter((rootPath, index, allPaths) => allPaths.indexOf(rootPath) === index)
				.slice(0, MAX_LOCAL_FILESYSTEM_ROOTS);
			if (nextLocalRootPaths.length === localRootPaths.length) return;
			const updated = await electronAPI.setAgentFilesystemSettings({
				mode: "desktop_local_folder",
				localRootPaths: nextLocalRootPaths,
			});
			setFilesystemSettings(updated);
		},
		[electronAPI, localRootPaths]
	);

	const runPickLocalRoot = useCallback(async () => {
		if (!electronAPI?.pickAgentFilesystemRoot) return;
		const picked = await electronAPI.pickAgentFilesystemRoot();
		if (!picked) return;
		await applyLocalRootPath(picked);
	}, [applyLocalRootPath, electronAPI]);

	const handlePickFilesystemRoot = useCallback(async () => {
		if (!canAddMoreLocalRoots) return;
		if (hasLocalFilesystemTrust()) {
			await runPickLocalRoot();
			return;
		}
		if (!electronAPI?.pickAgentFilesystemRoot) return;
		const picked = await electronAPI.pickAgentFilesystemRoot();
		if (!picked) return;
		setPendingLocalPath(picked);
		setLocalTrustDialogOpen(true);
	}, [canAddMoreLocalRoots, electronAPI, hasLocalFilesystemTrust, runPickLocalRoot]);

	const handleRemoveFilesystemRoot = useCallback(
		async (rootPathToRemove: string) => {
			if (!electronAPI?.setAgentFilesystemSettings) return;
			const updated = await electronAPI.setAgentFilesystemSettings({
				mode: "desktop_local_folder",
				localRootPaths: localRootPaths.filter((rootPath) => rootPath !== rootPathToRemove),
			});
			setFilesystemSettings(updated);
		},
		[electronAPI, localRootPaths]
	);

	const handleClearFilesystemRoots = useCallback(async () => {
		if (!electronAPI?.setAgentFilesystemSettings) return;
		const updated = await electronAPI.setAgentFilesystemSettings({
			mode: "desktop_local_folder",
			localRootPaths: [],
		});
		setFilesystemSettings(updated);
	}, [electronAPI]);

	const handleFilesystemTabChange = useCallback(
		async (tab: "cloud" | "local") => {
			if (!electronAPI?.setAgentFilesystemSettings) return;
			const updated = await electronAPI.setAgentFilesystemSettings({
				mode: tab === "cloud" ? "cloud" : "desktop_local_folder",
			});
			setFilesystemSettings(updated);
		},
		[electronAPI]
	);

	// AI File Sort state
	const { data: searchSpaces, refetch: refetchSearchSpaces } = useAtomValue(searchSpacesAtom);
	const activeSearchSpace = useMemo(
		() => searchSpaces?.find((s) => s.id === searchSpaceId),
		[searchSpaces, searchSpaceId]
	);
	const aiSortEnabled = activeSearchSpace?.ai_file_sort_enabled ?? false;
	const [aiSortBusy, setAiSortBusy] = useState(false);
	const [aiSortConfirmOpen, setAiSortConfirmOpen] = useState(false);

	const handleToggleAiSort = useCallback(() => {
		if (aiSortEnabled) {
			// Disable: just update the setting, no confirmation needed
			setAiSortBusy(true);
			searchSpacesApiService
				.updateSearchSpace({ id: searchSpaceId, data: { ai_file_sort_enabled: false } })
				.then(() => {
					refetchSearchSpaces();
					toast.success("AI file sorting disabled");
				})
				.catch(() => toast.error("Failed to disable AI file sorting"))
				.finally(() => setAiSortBusy(false));
		} else {
			setAiSortConfirmOpen(true);
		}
	}, [aiSortEnabled, searchSpaceId, refetchSearchSpaces]);

	const handleConfirmEnableAiSort = useCallback(() => {
		setAiSortConfirmOpen(false);
		setAiSortBusy(true);
		searchSpacesApiService
			.updateSearchSpace({ id: searchSpaceId, data: { ai_file_sort_enabled: true } })
			.then(() => searchSpacesApiService.triggerAiSort(searchSpaceId))
			.then(() => {
				refetchSearchSpaces();
				toast.success("AI file sorting enabled — organizing your documents in the background");
			})
			.catch(() => toast.error("Failed to enable AI file sorting"))
			.finally(() => setAiSortBusy(false));
	}, [searchSpaceId, refetchSearchSpaces]);

	const handleWatchLocalFolder = useCallback(async () => {
		const api = window.electronAPI;
		if (!api?.selectFolder) return;

		const folderPath = await api.selectFolder();
		if (!folderPath) return;

		const folderName = folderPath.split("/").pop() || folderPath.split("\\").pop() || folderPath;
		setWatchInitialFolder({ path: folderPath, name: folderName });
		setFolderWatchOpen(true);
	}, [setWatchInitialFolder, setFolderWatchOpen]);

	const refreshWatchedIds = useCallback(async () => {
		if (!electronAPI?.getWatchedFolders) return;
		const api = electronAPI;

		const folders = (await api.getWatchedFolders()) as WatchedFolderEntry[];

		if (folders.length === 0) {
			try {
				const backendFolders = await documentsApiService.getWatchedFolders(searchSpaceId);
				for (const bf of backendFolders) {
					const meta = bf.metadata as Record<string, unknown> | null;
					if (!meta?.watched || !meta.folder_path) continue;
					await api.addWatchedFolder({
						path: meta.folder_path as string,
						name: bf.name,
						rootFolderId: bf.id,
						searchSpaceId: bf.search_space_id,
						excludePatterns: (meta.exclude_patterns as string[]) ?? [],
						fileExtensions: (meta.file_extensions as string[] | null) ?? null,
						active: true,
					});
				}
				const recovered = (await api.getWatchedFolders()) as WatchedFolderEntry[];
				const ids = new Set(
					recovered
						.filter((f: WatchedFolderEntry) => f.rootFolderId != null)
						.map((f: WatchedFolderEntry) => f.rootFolderId as number)
				);
				setWatchedFolderIds(ids);
				return;
			} catch (err) {
				console.error("[DocumentsSidebar] Recovery from backend failed:", err);
			}
		}

		const ids = new Set(
			folders
				.filter((f: WatchedFolderEntry) => f.rootFolderId != null)
				.map((f: WatchedFolderEntry) => f.rootFolderId as number)
		);
		setWatchedFolderIds(ids);
	}, [searchSpaceId, electronAPI]);

	useEffect(() => {
		refreshWatchedIds();
	}, [refreshWatchedIds]);
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
	const [zeroFolders, zeroFoldersResult] = useQuery(queries.folders.bySpace({ searchSpaceId }));
	const [zeroAllDocs, zeroAllDocsResult] = useQuery(queries.documents.bySpace({ searchSpaceId }));
	const [agentCreatedDocs, setAgentCreatedDocs] = useAtom(agentCreatedDocumentsAtom);

	const treeFolders: FolderDisplay[] = useMemo(
		() =>
			(zeroFolders ?? []).map((f) => ({
				id: f.id,
				name: f.name,
				position: f.position,
				parentId: f.parentId ?? null,
				searchSpaceId: f.searchSpaceId,
				metadata: f.metadata as Record<string, unknown> | null | undefined,
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
			if (!electronAPI) return;

			const watchedFolders = (await electronAPI.getWatchedFolders()) as WatchedFolderEntry[];
			const matched = watchedFolders.find((wf: WatchedFolderEntry) => wf.rootFolderId === folder.id);
			if (!matched) {
				toast.error("This folder is not being watched");
				return;
			}

			try {
				toast.info(`Re-scanning folder: ${matched.name}`);
				await uploadFolderScan({
					folderPath: matched.path,
					folderName: matched.name,
					searchSpaceId,
					excludePatterns: matched.excludePatterns ?? DEFAULT_EXCLUDE_PATTERNS,
					fileExtensions: matched.fileExtensions ?? Array.from(getSupportedExtensionsSet()),
					enableSummary: false,
					rootFolderId: folder.id,
				});
				toast.success(`Re-scan complete: ${matched.name}`);
			} catch (err) {
				toast.error((err as Error)?.message || "Failed to re-scan folder");
			}
		},
		[searchSpaceId, electronAPI]
	);

	const handleStopWatching = useCallback(
		async (folder: FolderDisplay) => {
			if (!electronAPI) return;

			const watchedFolders = (await electronAPI.getWatchedFolders()) as WatchedFolderEntry[];
			const matched = watchedFolders.find((wf: WatchedFolderEntry) => wf.rootFolderId === folder.id);
			if (!matched) {
				toast.error("This folder is not being watched");
				return;
			}

			await electronAPI.removeWatchedFolder(matched.path);
			try {
				await foldersApiService.stopWatching(folder.id);
			} catch (err) {
				console.error("[DocumentsSidebar] Failed to clear watched metadata:", err);
			}
			toast.success(`Stopped watching: ${matched.name}`);
			refreshWatchedIds();
		},
		[electronAPI, refreshWatchedIds]
	);

	const handleRenameFolder = useCallback(async (folder: FolderDisplay, newName: string) => {
		try {
			await foldersApiService.updateFolder(folder.id, { name: newName });
			toast.success("Folder renamed");
		} catch (e: unknown) {
			toast.error((e as Error)?.message || "Failed to rename folder");
		}
	}, []);

	const handleDeleteFolder = useCallback(
		async (folder: FolderDisplay) => {
			if (!confirm(`Delete folder "${folder.name}" and all its contents?`)) return;
			try {
				if (electronAPI) {
					const watchedFolders = (await electronAPI.getWatchedFolders()) as WatchedFolderEntry[];
					const matched = watchedFolders.find(
						(wf: WatchedFolderEntry) => wf.rootFolderId === folder.id
					);
					if (matched) {
						await electronAPI.removeWatchedFolder(matched.path);
					}
				}
				await foldersApiService.deleteFolder(folder.id);
				toast.success("Folder deleted");
			} catch (e: unknown) {
				toast.error((e as Error)?.message || "Failed to delete folder");
			}
		},
		[electronAPI]
	);

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

	const isExportingKBRef = useRef(false);
	const [exportWarningOpen, setExportWarningOpen] = useState(false);
	const [exportWarningContext, setExportWarningContext] = useState<{
		folder: FolderDisplay;
		pendingCount: number;
	} | null>(null);

	const doExport = useCallback(async (url: string, downloadName: string) => {
		const response = await authenticatedFetch(url, { method: "GET" });
		if (!response.ok) {
			const errorData = await response.json().catch(() => ({ detail: "Export failed" }));
			throw new Error(errorData.detail || "Export failed");
		}

		const blob = await response.blob();
		const blobUrl = URL.createObjectURL(blob);
		const a = document.createElement("a");
		a.href = blobUrl;
		a.download = downloadName;
		document.body.appendChild(a);
		a.click();
		document.body.removeChild(a);
		URL.revokeObjectURL(blobUrl);
	}, []);

	const handleExportWarningConfirm = useCallback(async () => {
		setExportWarningOpen(false);
		const ctx = exportWarningContext;
		if (!ctx?.folder) return;

		isExportingKBRef.current = true;
		try {
			const safeName =
				ctx.folder.name
					.replace(/[^a-zA-Z0-9 _-]/g, "_")
					.trim()
					.slice(0, 80) || "folder";
			await doExport(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/search-spaces/${searchSpaceId}/export?folder_id=${ctx.folder.id}`,
				`${safeName}.zip`
			);
			toast.success(`Folder "${ctx.folder.name}" exported`);
		} catch (err) {
			console.error("Folder export failed:", err);
			toast.error(err instanceof Error ? err.message : "Export failed");
		} finally {
			isExportingKBRef.current = false;
		}
		setExportWarningContext(null);
	}, [exportWarningContext, searchSpaceId, doExport]);

	const getPendingCountInSubtree = useCallback(
		(folderId: number): number => {
			const subtreeIds = new Set<number>();
			function collect(id: number) {
				subtreeIds.add(id);
				for (const child of foldersByParent[String(id)] ?? []) {
					collect(child.id);
				}
			}
			collect(folderId);
			return treeDocuments.filter(
				(d) =>
					subtreeIds.has(d.folderId ?? -1) &&
					(d.status?.state === "pending" || d.status?.state === "processing")
			).length;
		},
		[foldersByParent, treeDocuments]
	);

	const handleExportFolder = useCallback(
		async (folder: FolderDisplay) => {
			const folderPendingCount = getPendingCountInSubtree(folder.id);
			if (folderPendingCount > 0) {
				setExportWarningContext({
					folder,
					pendingCount: folderPendingCount,
				});
				setExportWarningOpen(true);
				return;
			}

			isExportingKBRef.current = true;
			try {
				const safeName =
					folder.name
						.replace(/[^a-zA-Z0-9 _-]/g, "_")
						.trim()
						.slice(0, 80) || "folder";
				await doExport(
					`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/search-spaces/${searchSpaceId}/export?folder_id=${folder.id}`,
					`${safeName}.zip`
				);
				toast.success(`Folder "${folder.name}" exported`);
			} catch (err) {
				console.error("Folder export failed:", err);
				toast.error(err instanceof Error ? err.message : "Export failed");
			} finally {
				isExportingKBRef.current = false;
			}
		},
		[searchSpaceId, getPendingCountInSubtree, doExport]
	);

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
						d.status?.state !== "processing" &&
						d.status?.state !== "failed"
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
			const displayType = d.document_type === "LOCAL_FOLDER_FILE" ? "FILE" : d.document_type;
			counts[displayType] = (counts[displayType] || 0) + 1;
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

	const showFilesystemTabs = !isMobile && !!electronAPI && !!filesystemSettings;
	const currentFilesystemTab = filesystemSettings?.mode === "desktop_local_folder" ? "local" : "cloud";
	const showCloudSkeleton =
		currentFilesystemTab === "cloud" &&
		(zeroFoldersResult.type !== "complete" || zeroAllDocsResult.type !== "complete");

	const cloudContent = (
		<>
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

			{isElectron && (
				<button
					type="button"
					onClick={handleWatchLocalFolder}
					className="shrink-0 mx-4 mb-4 flex select-none items-center gap-2 rounded-lg border bg-muted/50 px-3 py-2 transition-colors hover:bg-muted/80"
				>
					<FolderClock className="size-4 shrink-0 text-muted-foreground" />
					<span className="truncate text-xs text-muted-foreground">Watch local folder</span>
				</button>
			)}

			<div className="flex-1 min-h-0 pt-0 flex flex-col">
				<div className="px-4 pb-2">
					<DocumentsFilters
						typeCounts={typeCounts}
						onSearch={setSearch}
						searchValue={search}
						onToggleType={onToggleType}
						activeTypes={activeTypes}
						onCreateFolder={() => handleCreateFolder(null)}
						aiSortEnabled={aiSortEnabled}
						aiSortBusy={aiSortBusy}
						onToggleAiSort={handleToggleAiSort}
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

					{showCloudSkeleton ? (
						<CloudDocumentsSkeleton />
					) : (
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
							onExportFolder={handleExportFolder}
						/>
					)}
				</div>
			</div>
		</>
	);

	const localContent = (
		<div className="flex min-h-0 flex-1 flex-col select-none">
			<div className="mx-4 mt-4 mb-3">
				<div className="flex h-7 w-full items-stretch rounded-lg border bg-muted/50 text-[11px] text-muted-foreground">
					{localRootPaths.length > 0 ? (
						<DropdownMenu>
							<DropdownMenuTrigger asChild>
								<button
									type="button"
									className="min-w-0 flex-1 flex items-center gap-1 rounded-l-lg px-2 text-left transition-colors hover:bg-muted/80 focus-visible:outline-none focus-visible:ring-0 focus-visible:ring-offset-0"
									title={localRootPaths.join("\n")}
									aria-label="Manage selected folders"
								>
									<Folder className="size-3 shrink-0 text-muted-foreground" />
									<span className="truncate">
										{localRootPaths.length === 1
											? "1 folder selected"
											: `${localRootPaths.length} folders selected`}
									</span>
								</button>
							</DropdownMenuTrigger>
							<DropdownMenuContent align="start" className="w-56 select-none p-0.5">
								<DropdownMenuLabel className="px-1.5 pt-1.5 pb-0.5 text-xs font-medium text-muted-foreground">
									Selected folders
								</DropdownMenuLabel>
								<DropdownMenuSeparator className="mx-1 my-0.5" />
								{localRootPaths.map((rootPath) => (
									<DropdownMenuItem
										key={rootPath}
										onSelect={(event) => event.preventDefault()}
										className="group h-8 gap-1.5 px-1.5 text-sm text-foreground"
									>
										<Folder className="size-3.5 text-muted-foreground" />
										<span className="min-w-0 flex-1 truncate">
											{getFolderDisplayName(rootPath)}
										</span>
										<button
											type="button"
											className="inline-flex size-5 items-center justify-center rounded text-muted-foreground transition-colors hover:text-foreground"
											onClick={(event) => {
												event.stopPropagation();
												void handleRemoveFilesystemRoot(rootPath);
											}}
											aria-label={`Remove ${getFolderDisplayName(rootPath)}`}
										>
											<X className="size-3" />
										</button>
									</DropdownMenuItem>
								))}
								<DropdownMenuSeparator className="mx-1 my-0.5" />
								<DropdownMenuItem
									variant="destructive"
									className="h-8 px-1.5 text-xs text-destructive focus:text-destructive"
									onClick={() => {
										void handleClearFilesystemRoots();
									}}
								>
									Clear all folders
								</DropdownMenuItem>
							</DropdownMenuContent>
						</DropdownMenu>
					) : (
						<div
							className="min-w-0 flex-1 flex items-center gap-1 px-2"
							title="No local folders selected"
						>
							<Folder className="size-3 shrink-0 text-muted-foreground" />
							<span className="truncate">No local folders selected</span>
						</div>
					)}
					<Separator
						orientation="vertical"
						className="data-[orientation=vertical]:h-3 self-center bg-border"
					/>
					{electronAPI ? (
						<Tooltip>
							<TooltipTrigger asChild>
								<span className="inline-flex">
									<button
										type="button"
										className="flex w-8 items-center justify-center rounded-r-lg text-muted-foreground transition-colors hover:bg-muted/80 hover:text-foreground focus-visible:outline-none focus-visible:ring-0 focus-visible:ring-offset-0 disabled:opacity-50"
										onClick={() => {
											void handlePickFilesystemRoot();
										}}
										disabled={!canAddMoreLocalRoots}
										aria-label="Add folder"
									>
										<FolderPlus className="size-3.5" />
									</button>
								</span>
							</TooltipTrigger>
							<TooltipContent side="top" className="text-xs">
								{canAddMoreLocalRoots
									? "Add folder"
									: `You can add up to ${MAX_LOCAL_FILESYSTEM_ROOTS} folders`}
							</TooltipContent>
						</Tooltip>
					) : (
						<button
							type="button"
							className="flex w-8 items-center justify-center rounded-r-lg text-muted-foreground transition-colors hover:bg-muted/80 hover:text-foreground focus-visible:outline-none focus-visible:ring-0 focus-visible:ring-offset-0 disabled:opacity-50"
							onClick={() => {
								void handlePickFilesystemRoot();
							}}
							disabled={!canAddMoreLocalRoots}
							aria-label="Add folder"
						>
							<FolderPlus className="size-3.5" />
						</button>
					)}
				</div>
			</div>
			<div className="mx-4 mb-2">
				<div className="relative flex-1 min-w-0">
					<div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-muted-foreground">
						<Search size={13} aria-hidden="true" />
					</div>
					<Input
						ref={localSearchInputRef}
						className="peer h-8 w-full pl-8 pr-8 text-sm bg-sidebar border-border/60 select-none focus:select-text"
						value={localSearch}
						onChange={(e) => setLocalSearch(e.target.value)}
						placeholder="Search local files"
						type="text"
						aria-label="Search local files"
					/>
					{Boolean(localSearch) && (
						<button
							type="button"
							className="absolute inset-y-0 right-0 flex h-full w-8 items-center justify-center rounded-r-md text-muted-foreground hover:text-foreground transition-colors"
							aria-label="Clear local search"
							onClick={() => {
								setLocalSearch("");
								localSearchInputRef.current?.focus();
							}}
						>
							<X size={13} strokeWidth={2} aria-hidden="true" />
						</button>
					)}
				</div>
			</div>
			<LocalFilesystemBrowser
				rootPaths={localRootPaths}
				searchSpaceId={searchSpaceId}
				searchQuery={debouncedLocalSearch.trim() || undefined}
				onOpenFile={(localFilePath) => {
					openEditorPanel({
						kind: "local_file",
						localFilePath,
						title: localFilePath.split("/").pop() || localFilePath,
						searchSpaceId,
					});
				}}
			/>
		</div>
	);

	const documentsContent = (
		<>
			<div className="shrink-0 flex h-14 items-center px-4">
				<div className="flex w-full items-center justify-between">
					<div className="flex items-center gap-3">
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
						{showFilesystemTabs && (
							<Tabs
								value={currentFilesystemTab}
								onValueChange={(value) => {
									void handleFilesystemTabChange(value === "local" ? "local" : "cloud");
								}}
							>
								<TabsList className="h-6 gap-0 rounded-md bg-muted/60 p-0.5 select-none">
									<TabsTrigger
										value="cloud"
										className="h-5 gap-1 px-1.5 text-[11px] select-none focus-visible:ring-0 focus-visible:ring-offset-0 data-[state=active]:bg-muted-foreground/25 data-[state=active]:text-foreground data-[state=active]:shadow-none"
										title="Cloud"
									>
										<Server className="size-3 shrink-0" />
										<span className="leading-none">Cloud</span>
									</TabsTrigger>
									<TabsTrigger
										value="local"
										className="h-5 gap-1 px-1.5 text-[11px] select-none focus-visible:ring-0 focus-visible:ring-offset-0 data-[state=active]:bg-muted-foreground/25 data-[state=active]:text-foreground data-[state=active]:shadow-none"
										title="Local"
									>
										<Laptop className="size-3 shrink-0" />
										<span className="leading-none">Local</span>
									</TabsTrigger>
								</TabsList>
							</Tabs>
						)}
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
			{showFilesystemTabs ? (
				<Tabs
					value={currentFilesystemTab}
					onValueChange={(value) => {
						void handleFilesystemTabChange(value === "local" ? "local" : "cloud");
					}}
					className="flex min-h-0 flex-1 flex-col"
				>
					<TabsContent value="cloud" className="mt-0 flex min-h-0 flex-1 flex-col">
						{cloudContent}
					</TabsContent>
					<TabsContent value="local" className="mt-0 flex min-h-0 flex-1 flex-col">
						{localContent}
					</TabsContent>
				</Tabs>
			) : (
				cloudContent
			)}

			{versionDocId !== null && (
				<VersionHistoryDialog
					open
					onOpenChange={(open) => {
						if (!open) setVersionDocId(null);
					}}
					documentId={versionDocId}
				/>
			)}

			{isElectron && (
				<FolderWatchDialog
					open={folderWatchOpen}
					onOpenChange={(nextOpen) => {
						setFolderWatchOpen(nextOpen);
						if (!nextOpen) setWatchInitialFolder(null);
					}}
					searchSpaceId={searchSpaceId}
					initialFolder={watchInitialFolder}
					onSuccess={refreshWatchedIds}
				/>
			)}
			<AlertDialog
				open={localTrustDialogOpen}
				onOpenChange={(nextOpen) => {
					setLocalTrustDialogOpen(nextOpen);
					if (!nextOpen) setPendingLocalPath(null);
				}}
			>
				<AlertDialogContent className="sm:max-w-md select-none">
					<AlertDialogHeader>
						<AlertDialogTitle>Trust this workspace?</AlertDialogTitle>
						<AlertDialogDescription>
							Local mode can read and edit files inside the folders you select. Continue only if
							you trust this workspace and its contents.
						</AlertDialogDescription>
						{pendingLocalPath && (
							<AlertDialogDescription className="mt-1 whitespace-pre-wrap break-words font-mono text-xs">
								Folder path: {pendingLocalPath}
							</AlertDialogDescription>
						)}
					</AlertDialogHeader>
					<AlertDialogFooter>
						<AlertDialogCancel>Cancel</AlertDialogCancel>
						<AlertDialogAction
							onClick={async () => {
								try {
									window.localStorage.setItem(LOCAL_FILESYSTEM_TRUST_KEY, "true");
								} catch {}
								setLocalTrustDialogOpen(false);
								const path = pendingLocalPath;
								setPendingLocalPath(null);
								if (path) {
									await applyLocalRootPath(path);
								} else {
									await runPickLocalRoot();
								}
							}}
						>
							I trust this workspace
						</AlertDialogAction>
					</AlertDialogFooter>
				</AlertDialogContent>
			</AlertDialog>

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

			<AlertDialog
				open={exportWarningOpen}
				onOpenChange={(open) => {
					if (!open) {
						setExportWarningOpen(false);
						setExportWarningContext(null);
					}
				}}
			>
				<AlertDialogContent>
					<AlertDialogHeader>
						<AlertDialogTitle>Some documents are still processing</AlertDialogTitle>
						<AlertDialogDescription>
							{exportWarningContext?.pendingCount} document
							{exportWarningContext?.pendingCount !== 1 ? "s are" : " is"} currently being processed
							and will be excluded from the export. Do you want to continue?
						</AlertDialogDescription>
					</AlertDialogHeader>
					<AlertDialogFooter>
						<AlertDialogCancel>Cancel</AlertDialogCancel>
						<AlertDialogAction onClick={handleExportWarningConfirm}>
							Export anyway
						</AlertDialogAction>
					</AlertDialogFooter>
				</AlertDialogContent>
			</AlertDialog>

			<AlertDialog open={aiSortConfirmOpen} onOpenChange={setAiSortConfirmOpen}>
				<AlertDialogContent>
					<AlertDialogHeader>
						<AlertDialogTitle>Enable AI File Sorting?</AlertDialogTitle>
						<AlertDialogDescription>
							All documents in this search space will be organized into folders by connector type,
							date, and AI-generated categories. New documents will also be sorted automatically.
							You can disable this at any time.
						</AlertDialogDescription>
					</AlertDialogHeader>
					<AlertDialogFooter>
						<AlertDialogCancel>Cancel</AlertDialogCancel>
						<AlertDialogAction onClick={handleConfirmEnableAiSort}>Enable</AlertDialogAction>
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

// ---------------------------------------------------------------------------
// Anonymous Documents Sidebar
// ---------------------------------------------------------------------------

const ANON_ALLOWED_EXTENSIONS = new Set([
	".md",
	".markdown",
	".txt",
	".text",
	".json",
	".jsonl",
	".yaml",
	".yml",
	".toml",
	".ini",
	".cfg",
	".conf",
	".xml",
	".css",
	".scss",
	".py",
	".js",
	".jsx",
	".ts",
	".tsx",
	".java",
	".kt",
	".go",
	".rs",
	".rb",
	".php",
	".c",
	".h",
	".cpp",
	".hpp",
	".cs",
	".swift",
	".sh",
	".sql",
	".log",
	".rst",
	".tex",
	".vue",
	".svelte",
	".astro",
	".tf",
	".proto",
	".csv",
	".tsv",
	".html",
	".htm",
	".xhtml",
]);

const ANON_ACCEPT = Array.from(ANON_ALLOWED_EXTENSIONS).join(",");

function AnonymousDocumentsSidebar({
	open,
	onOpenChange,
	isDocked = false,
	onDockedChange,
	embedded = false,
	headerAction,
}: DocumentsSidebarProps) {
	const t = useTranslations("documents");
	const tSidebar = useTranslations("sidebar");
	const isMobile = !useMediaQuery("(min-width: 640px)");
	const setRightPanelCollapsed = useSetAtom(rightPanelCollapsedAtom);
	const anonMode = useAnonymousMode();
	const { gate } = useLoginGate();

	const fileInputRef = useRef<HTMLInputElement>(null);
	const [isUploading, setIsUploading] = useState(false);
	const [search, setSearch] = useState("");

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

	const uploadedDoc = anonMode.isAnonymous ? anonMode.uploadedDoc : null;
	const hasDoc = uploadedDoc !== null;

	const handleAnonUploadClick = useCallback(() => {
		if (hasDoc) {
			gate("upload more documents");
			return;
		}
		fileInputRef.current?.click();
	}, [hasDoc, gate]);

	const handleFileChange = useCallback(
		async (e: React.ChangeEvent<HTMLInputElement>) => {
			const file = e.target.files?.[0];
			if (!file) return;
			e.target.value = "";

			const ext = `.${file.name.split(".").pop()?.toLowerCase()}`;
			if (!ANON_ALLOWED_EXTENSIONS.has(ext)) {
				gate("upload PDFs, Word documents, images, and more");
				return;
			}

			setIsUploading(true);
			try {
				const result = await anonymousChatApiService.uploadDocument(file);
				if (!result.ok) {
					if (result.reason === "quota_exceeded") gate("upload more documents");
					return;
				}
				const data = result.data;
				if (anonMode.isAnonymous) {
					anonMode.setUploadedDoc({
						filename: data.filename,
						sizeBytes: data.size_bytes,
					});
				}
				toast.success(`Uploaded "${data.filename}"`);
			} catch (err) {
				console.error("Upload failed:", err);
				toast.error(err instanceof Error ? err.message : "Upload failed");
			} finally {
				setIsUploading(false);
			}
		},
		[gate, anonMode]
	);

	const handleRemoveDoc = useCallback(() => {
		if (anonMode.isAnonymous) {
			anonMode.setUploadedDoc(null);
		}
	}, [anonMode]);

	const treeDocuments: DocumentNodeDoc[] = useMemo(() => {
		if (!anonMode.isAnonymous || !anonMode.uploadedDoc) return [];
		return [
			{
				id: -1,
				title: anonMode.uploadedDoc.filename,
				document_type: "FILE",
				folderId: null,
				status: { state: "ready" } as { state: string; reason?: string | null },
			},
		];
	}, [anonMode]);

	const searchFilteredDocs = useMemo(() => {
		const q = search.trim().toLowerCase();
		if (!q) return treeDocuments;
		return treeDocuments.filter((d) => d.title.toLowerCase().includes(q));
	}, [treeDocuments, search]);

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
			<input
				ref={fileInputRef}
				type="file"
				accept={ANON_ACCEPT}
				className="hidden"
				onChange={handleFileChange}
				disabled={isUploading}
			/>

			{/* Header */}
			<div className="shrink-0 flex h-14 items-center px-4">
				<div className="flex w-full items-center justify-between">
					<div className="flex items-center gap-2">
						<h2 className="select-none text-lg font-semibold">{t("title") || "Documents"}</h2>
					</div>
					<div className="flex items-center gap-1">
						{isMobile && (
							<Button
								variant="ghost"
								size="icon"
								className="h-8 w-8 rounded-full"
								onClick={() => onOpenChange(false)}
							>
								<X className="h-4 w-4 text-muted-foreground" />
								<span className="sr-only">{tSidebar("close") || "Close"}</span>
							</Button>
						)}
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

			{/* Connectors strip (gated) */}
			<div className="shrink-0 mx-4 mt-4 mb-4 flex select-none items-center gap-2 rounded-lg border bg-muted/50 transition-colors hover:bg-muted/80">
				<button
					type="button"
					onClick={() => gate("connect your data sources")}
					className="flex items-center gap-2 min-w-0 flex-1 text-left px-3 py-2"
				>
					<Unplug className="size-4 shrink-0 text-muted-foreground" />
					<span className="truncate text-xs text-muted-foreground">Connect your connectors</span>
					<AvatarGroup className="ml-auto shrink-0">
						{(isMobile ? SHOWCASE_CONNECTORS.slice(0, 5) : SHOWCASE_CONNECTORS).map(
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

			{/* Filters & upload */}
			<div className="flex-1 min-h-0 pt-0 flex flex-col">
				<div className="px-4 pb-2">
					<DocumentsFilters
						typeCounts={hasDoc ? { FILE: 1 } : {}}
						onSearch={setSearch}
						searchValue={search}
						onToggleType={() => {}}
						activeTypes={[]}
						onCreateFolder={() => gate("create folders")}
						aiSortEnabled={false}
						onUploadClick={handleAnonUploadClick}
					/>
				</div>

				<div className="relative flex-1 min-h-0 overflow-auto">
					<FolderTreeView
						folders={[]}
						documents={searchFilteredDocs}
						expandedIds={new Set()}
						onToggleExpand={() => {}}
						mentionedDocIds={mentionedDocIds}
						onToggleChatMention={handleToggleChatMention}
						onToggleFolderSelect={() => {}}
						onRenameFolder={() => gate("rename folders")}
						onDeleteFolder={() => gate("delete folders")}
						onMoveFolder={() => gate("organize folders")}
						onCreateFolder={() => gate("create folders")}
						searchQuery={search.trim() || undefined}
						onPreviewDocument={() => gate("preview documents")}
						onEditDocument={() => gate("edit documents")}
						onDeleteDocument={async () => {
							handleRemoveDoc();
							setSidebarDocs((prev) => prev.filter((d) => d.id !== -1));
							return true;
						}}
						onMoveDocument={() => gate("organize documents")}
						onExportDocument={() => gate("export documents")}
						onVersionHistory={() => gate("view version history")}
						activeTypes={[]}
						onDropIntoFolder={async () => gate("organize documents")}
						onReorderFolder={async () => gate("organize folders")}
						watchedFolderIds={new Set()}
						onRescanFolder={() => gate("watch local folders")}
						onStopWatchingFolder={() => gate("watch local folders")}
						onExportFolder={() => gate("export folders")}
					/>

					{!hasDoc && (
						<div className="px-4 py-8 text-center">
							<button
								type="button"
								onClick={handleAnonUploadClick}
								disabled={isUploading}
								className="flex w-full items-center justify-center gap-2 rounded-lg border-2 border-dashed border-primary/30 px-4 py-6 text-sm text-primary transition-colors hover:border-primary/60 hover:bg-primary/5 cursor-pointer disabled:opacity-50 disabled:pointer-events-none"
							>
								<Upload className="size-4" />
								{isUploading ? "Uploading..." : "Upload a document"}
							</button>
							<p className="mt-2 text-[11px] text-muted-foreground leading-relaxed">
								Text, code, CSV, and HTML files only. Create an account for PDFs, images, and 30+
								connectors.
							</p>
						</div>
					)}
				</div>
			</div>

			{/* CTA footer */}
			<div className="border-t p-4 space-y-3">
				<div className="flex items-center gap-2 text-xs text-muted-foreground">
					<Lock className="size-3.5 shrink-0" />
					<span>Create an account to unlock:</span>
				</div>
				<ul className="space-y-1.5 text-xs text-muted-foreground pl-5">
					<li className="flex items-center gap-1.5">
						<Paperclip className="size-3 shrink-0" /> PDF, Word, images, audio uploads
					</li>
					<li className="flex items-center gap-1.5">
						<FileText className="size-3 shrink-0" /> Unlimited documents
					</li>
				</ul>
				<Button size="sm" className="w-full" asChild>
					<Link href="/register">Create Free Account</Link>
				</Button>
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

	if (isMobile) {
		return (
			<Drawer open={open} onOpenChange={onOpenChange}>
				<DrawerContent className="max-h-[75vh] flex flex-col">
					<DrawerTitle className="sr-only">{t("title") || "Documents"}</DrawerTitle>
					<DrawerHandle />
					<div className="flex-1 min-h-0 flex flex-col overflow-hidden">{documentsContent}</div>
				</DrawerContent>
			</Drawer>
		);
	}

	return (
		<SidebarSlideOutPanel
			open={open}
			onOpenChange={onOpenChange}
			ariaLabel={t("title") || "Documents"}
			width={380}
		>
			{documentsContent}
		</SidebarSlideOutPanel>
	);
}
