"use client";

import { useQuery } from "@rocicorp/zero/react";
import { useAtom, useAtomValue, useSetAtom } from "jotai";
import {
	Check,
	FilePlus,
	FolderPlus,
	FolderSync,
	ListFilter,
	Plus,
	Settings2,
	SlidersVertical,
	Trash2,
	Upload,
} from "lucide-react";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { makeFolderMention, mentionedDocumentsAtom } from "@/atoms/chat/mentioned-documents.atom";
import { importConnectorRequestAtom } from "@/atoms/connector-dialog/connector-dialog.atoms";
import { connectorsAtom } from "@/atoms/connectors/connector-query.atoms";
import { deleteDocumentMutationAtom } from "@/atoms/documents/document-mutation.atoms";
import { expandedFolderIdsAtom } from "@/atoms/documents/folder.atoms";
import { agentCreatedDocumentsAtom } from "@/atoms/documents/ui.atoms";
import { openEditorPanelAtom } from "@/atoms/editor/editor-panel.atom";
import { useConnectorStatus } from "@/components/assistant-ui/connector-popup/hooks/use-connector-status";
import { useDocumentUploadDialog } from "@/components/assistant-ui/document-upload-popup";
import { CreateFolderDialog } from "@/components/documents/CreateFolderDialog";
import type { DocumentNodeDoc } from "@/components/documents/DocumentNode";
import { getDocumentTypeIcon } from "@/components/documents/DocumentTypeIcon";
import type { FolderDisplay } from "@/components/documents/FolderNode";
import { FolderPickerDialog } from "@/components/documents/FolderPickerDialog";
import { FolderTreeView } from "@/components/documents/FolderTreeView";
import { VersionHistoryDialog } from "@/components/documents/version-history";
import { useOptionalRuntimeConfig, useRuntimeConfig } from "@/components/providers/runtime-config";
import { EXPORT_FILE_EXTENSIONS } from "@/components/shared/ExportMenuItems";
import {
	DEFAULT_EXCLUDE_PATTERNS,
	FolderWatchDialog,
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
import { Button } from "@/components/ui/button";
import { Drawer, DrawerContent, DrawerHandle, DrawerTitle } from "@/components/ui/drawer";
import {
	DropdownMenu,
	DropdownMenuCheckboxItem,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuSeparator,
	DropdownMenuSub,
	DropdownMenuSubContent,
	DropdownMenuSubTrigger,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { useAnonymousMode, useIsAnonymous } from "@/contexts/anonymous-mode";
import { useLoginGate } from "@/contexts/login-gate";
import { EnumConnectorName } from "@/contracts/enums/connector";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";
import type { SearchSourceConnector } from "@/contracts/types/connector.types";
import type { DocumentTypeEnum } from "@/contracts/types/document.types";
import { useIsMobile } from "@/hooks/use-mobile";
import { useElectronAPI, usePlatform } from "@/hooks/use-platform";
import { documentsApiService } from "@/lib/apis/documents-api.service";
import { foldersApiService } from "@/lib/apis/folders-api.service";
import { authenticatedFetch } from "@/lib/auth-fetch";
import { getMentionDocKey } from "@/lib/chat/mention-doc-key";
import { getDocumentTypeLabel } from "@/lib/documents/document-type-labels";
import { buildBackendUrl } from "@/lib/env-config";
import { uploadFolderScan } from "@/lib/folder-sync-upload";
import { getWorkspaceIdNumber } from "@/lib/route-params";
import { getSupportedExtensionsSet } from "@/lib/supported-extensions";
import { queries } from "@/zero/queries/index";
import { SidebarSection } from "./SidebarSection";

const NON_DELETABLE_DOCUMENT_TYPES: readonly string[] = ["USER_MEMORY", "TEAM_MEMORY"];
const MEMORY_DOCUMENTS: DocumentNodeDoc[] = [
	{
		id: -1001,
		title: "MEMORY.md",
		document_type: "USER_MEMORY",
		folderId: null,
		status: { state: "ready" },
	},
	{
		id: -1002,
		title: "TEAM_MEMORY.md",
		document_type: "TEAM_MEMORY",
		folderId: null,
		status: { state: "ready" },
	},
];

function isMemoryDocument(doc: { document_type: string }) {
	return doc.document_type === "USER_MEMORY" || doc.document_type === "TEAM_MEMORY";
}

function downloadTextFile(content: string, fileName: string, type = "text/markdown;charset=utf-8") {
	const blob = new Blob([content], { type });
	const url = URL.createObjectURL(blob);
	const a = document.createElement("a");
	a.href = url;
	a.download = fileName;
	document.body.appendChild(a);
	a.click();
	document.body.removeChild(a);
	URL.revokeObjectURL(url);
}

export function EmbeddedDocumentsMenu({
	typeCounts,
	activeTypes,
	onToggleType,
	onCreateFolder,
}: {
	typeCounts: Partial<Record<string, number>>;
	activeTypes: DocumentTypeEnum[];
	onToggleType: (type: DocumentTypeEnum, checked: boolean) => void;
	onCreateFolder: () => void;
}) {
	const isMobile = useIsMobile();
	const [filterDrawerOpen, setFilterDrawerOpen] = useState(false);
	const documentTypes = useMemo(
		() => Object.keys(typeCounts).sort() as DocumentTypeEnum[],
		[typeCounts]
	);

	return (
		<>
			<DropdownMenu>
				<DropdownMenuTrigger asChild>
					<Button
						type="button"
						variant="ghost"
						size="icon"
						className="relative h-6 w-6 text-muted-foreground hover:bg-accent hover:text-accent-foreground"
						aria-label="Document actions"
					>
						<SlidersVertical className="size-3.5" />
						{activeTypes.length > 0 ? (
							<span className="absolute right-0.5 top-0.5 h-1.5 w-1.5 rounded-full bg-primary" />
						) : null}
					</Button>
				</DropdownMenuTrigger>
				<DropdownMenuContent align="end" className="w-44">
					<DropdownMenuItem onSelect={onCreateFolder}>
						<FolderPlus className="h-4 w-4" />
						New folder
					</DropdownMenuItem>
					{isMobile ? (
						<DropdownMenuItem onSelect={() => setFilterDrawerOpen(true)}>
							<ListFilter className="h-4 w-4" />
							<span className="flex-1">Filter by type</span>
						</DropdownMenuItem>
					) : (
						<DropdownMenuSub>
							<DropdownMenuSubTrigger>
								<ListFilter className="h-4 w-4" />
								Filter by type
							</DropdownMenuSubTrigger>
							<DropdownMenuSubContent className="w-52 max-h-72 overflow-y-auto">
								{documentTypes.length > 0 ? (
									documentTypes.map((type) => (
										<DropdownMenuCheckboxItem
											key={type}
											checked={activeTypes.includes(type)}
											onCheckedChange={(checked) => onToggleType(type, checked === true)}
											onSelect={(event) => event.preventDefault()}
										>
											{getDocumentTypeIcon(type, "h-4 w-4")}
											<span className="min-w-0 flex-1 truncate">{getDocumentTypeLabel(type)}</span>
											<span className="ml-auto text-xs text-muted-foreground">
												{typeCounts[type] ?? 0}
											</span>
										</DropdownMenuCheckboxItem>
									))
								) : (
									<DropdownMenuItem disabled>No document types</DropdownMenuItem>
								)}
							</DropdownMenuSubContent>
						</DropdownMenuSub>
					)}
				</DropdownMenuContent>
			</DropdownMenu>

			<Drawer
				open={filterDrawerOpen}
				onOpenChange={setFilterDrawerOpen}
				shouldScaleBackground={false}
			>
				<DrawerContent
					className="z-80 max-h-[75vh] rounded-t-2xl border bg-popover text-popover-foreground"
					overlayClassName="z-80"
				>
					<DrawerHandle className="mt-3 h-1.5 w-10" />
					<DrawerTitle className="px-4 pb-2 pt-3 text-center text-base font-semibold">
						Filter by type
					</DrawerTitle>
					<div className="px-4 pb-6 pt-1">
						{documentTypes.length > 0 ? (
							documentTypes.map((type, index) => {
								const isActive = activeTypes.includes(type);
								return (
									<div key={type}>
										{index > 0 && <div className="mx-3 h-px bg-popover-border" />}
										<button
											type="button"
											className="flex h-12 w-full items-center gap-3 rounded-lg px-3 text-left text-sm transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
											onClick={() => onToggleType(type, !isActive)}
										>
											{getDocumentTypeIcon(type, "h-4 w-4")}
											<span className="min-w-0 flex-1 truncate">{getDocumentTypeLabel(type)}</span>
											<span className="text-xs text-muted-foreground">{typeCounts[type] ?? 0}</span>
											{isActive && <Check className="h-4 w-4 shrink-0 text-primary" />}
										</button>
									</div>
								);
							})
						) : (
							<p className="px-3 py-4 text-sm text-muted-foreground">No document types</p>
						)}
					</div>
				</DrawerContent>
			</Drawer>
		</>
	);
}

/**
 * Import menu: local file upload plus the cloud-drive import connectors
 * (Google Drive / OneDrive / Dropbox). Drive/OneDrive/Dropbox set
 * `importConnectorRequestAtom`, which the connector dialog consumes to run
 * OAuth or open the existing account's config. In anonymous mode, `gate`
 * intercepts every item to trigger the login flow.
 */
export function EmbeddedImportMenu({
	gate,
	onFolderWatched,
}: {
	gate?: (feature: string) => void;
	onFolderWatched?: () => void;
}) {
	const { openDialog } = useDocumentUploadDialog();
	const setImportRequest = useSetAtom(importConnectorRequestAtom);
	// Provider is absent on anonymous /free pages, where every item is login-gated
	// anyway — defaulting to hosted (Composio) there is cosmetic.
	const selfHosted = useOptionalRuntimeConfig()?.deploymentMode === "self-hosted";
	const { isConnectorEnabled, getConnectorStatusMessage } = useConnectorStatus();
	const { data: connectors } = useAtomValue(connectorsAtom);

	// Watch Local Folder is a desktop-app feature (needs the Electron folder watcher).
	const { isDesktop } = usePlatform();
	const params = useParams();
	const workspaceId = getWorkspaceIdNumber(params) ?? 0;
	const [folderWatchOpen, setFolderWatchOpen] = useState(false);

	// Native Google Drive connector self-hosted only; hosted deployments use Composio.
	const driveType = selfHosted
		? EnumConnectorName.GOOGLE_DRIVE_CONNECTOR
		: EnumConnectorName.COMPOSIO_GOOGLE_DRIVE_CONNECTOR;

	const cloudItems = [
		{ type: driveType, label: "Google Drive" },
		{ type: EnumConnectorName.ONEDRIVE_CONNECTOR, label: "OneDrive" },
		{ type: EnumConnectorName.DROPBOX_CONNECTOR, label: "Dropbox" },
	];

	return (
		<DropdownMenu>
			<DropdownMenuTrigger asChild>
				<Button
					type="button"
					variant="ghost"
					size="icon"
					className="h-6 w-6 text-muted-foreground hover:bg-accent hover:text-accent-foreground"
					aria-label="Import documents"
				>
					<FilePlus className="size-3.5" />
				</Button>
			</DropdownMenuTrigger>
			<DropdownMenuContent align="end" className="w-56">
				<DropdownMenuItem onSelect={() => (gate ? gate("upload files") : openDialog())}>
					<Upload className="h-4 w-4" />
					Upload Files
				</DropdownMenuItem>
				{isDesktop && (
					<DropdownMenuItem
						onSelect={() => (gate ? gate("watch local folders") : setFolderWatchOpen(true))}
					>
						<FolderSync className="h-4 w-4" />
						Watch Local Folder
					</DropdownMenuItem>
				)}
				<DropdownMenuSeparator />
				{cloudItems.map((item) => {
					const enabled = gate ? true : isConnectorEnabled(item.type);
					const statusMessage = enabled ? null : getConnectorStatusMessage(item.type);
					const icon = getConnectorIcon(item.type, "h-4 w-4");
					// gate = anonymous mode; treat every connector as unconnected so items
					// route through the login gate rather than reading workspace connectors.
					const accountCount = gate
						? 0
						: (connectors ?? []).filter(
								(c: SearchSourceConnector) => c.connector_type === item.type
							).length;

					// Unavailable (e.g. maintenance): non-actionable item explaining why.
					if (!enabled) {
						return (
							<DropdownMenuItem key={item.type} disabled title={statusMessage ?? undefined}>
								{icon}
								{item.label}
							</DropdownMenuItem>
						);
					}

					// Connected: manage the existing account(s) or add another.
					if (accountCount > 0) {
						return (
							<DropdownMenuSub key={item.type}>
								<DropdownMenuSubTrigger>
									{icon}
									<span className="min-w-0 flex-1 truncate">{item.label}</span>
									<span className="ml-auto text-xs text-muted-foreground">{accountCount}</span>
								</DropdownMenuSubTrigger>
								<DropdownMenuSubContent className="w-48">
									<DropdownMenuItem
										onSelect={() =>
											gate
												? gate("manage import connectors")
												: setImportRequest({ connectorType: item.type, mode: "auto" })
										}
									>
										<Settings2 className="h-4 w-4" />
										{accountCount > 1 ? "Manage accounts" : "Manage"}
									</DropdownMenuItem>
									<DropdownMenuItem
										onSelect={() =>
											gate
												? gate("import from cloud storage")
												: setImportRequest({ connectorType: item.type, mode: "connect" })
										}
									>
										<Plus className="h-4 w-4" />
										Add another account
									</DropdownMenuItem>
								</DropdownMenuSubContent>
							</DropdownMenuSub>
						);
					}

					// Not connected: single click starts the first OAuth connect.
					return (
						<DropdownMenuItem
							key={item.type}
							onSelect={() =>
								gate
									? gate("import from cloud storage")
									: setImportRequest({ connectorType: item.type, mode: "auto" })
							}
						>
							{icon}
							{item.label}
						</DropdownMenuItem>
					);
				})}
			</DropdownMenuContent>
			{isDesktop && !gate && (
				<FolderWatchDialog
					open={folderWatchOpen}
					onOpenChange={setFolderWatchOpen}
					workspaceId={workspaceId}
					onSuccess={onFolderWatched}
				/>
			)}
		</DropdownMenu>
	);
}

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
		<div className="px-2 py-1">
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

interface WatchedFolderEntry {
	path: string;
	name: string;
	excludePatterns: string[];
	fileExtensions: string[] | null;
	rootFolderId: number | null;
	workspaceId: number;
	active: boolean;
}

interface DocumentsSidebarProps {
	/** When true, renders content without any wrapper — parent provides the container */
	embedded?: boolean;
}

export function DocumentsSidebar(props: DocumentsSidebarProps) {
	const isAnonymous = useIsAnonymous();
	const { isDesktop } = usePlatform();
	if (isAnonymous) {
		return <AnonymousDocumentsSidebar {...props} />;
	}
	return isDesktop ? (
		<AuthenticatedDesktopDocumentsSidebar {...props} />
	) : (
		<AuthenticatedWebDocumentsSidebar {...props} />
	);
}

function AuthenticatedDesktopDocumentsSidebar(props: DocumentsSidebarProps) {
	return <AuthenticatedDocumentsSidebarBase {...props} desktopFeaturesEnabled />;
}

function AuthenticatedWebDocumentsSidebar(props: DocumentsSidebarProps) {
	return <AuthenticatedDocumentsSidebarBase {...props} desktopFeaturesEnabled={false} />;
}

function AuthenticatedDocumentsSidebarBase({
	embedded = false,
	desktopFeaturesEnabled,
}: DocumentsSidebarProps & { desktopFeaturesEnabled: boolean }) {
	const t = useTranslations("documents");
	const params = useParams();
	const platformElectronAPI = useElectronAPI();
	const electronAPI = desktopFeaturesEnabled ? platformElectronAPI : null;
	const { etlService } = useRuntimeConfig();
	const workspaceId = getWorkspaceIdNumber(params) ?? 0;
	const openEditorPanel = useSetAtom(openEditorPanelAtom);

	const [activeTypes, setActiveTypes] = useState<DocumentTypeEnum[]>([]);
	const [watchedFolderIds, setWatchedFolderIds] = useState<Set<number>>(new Set());

	const refreshWatchedIds = useCallback(async () => {
		if (!electronAPI?.getWatchedFolders) return;
		const api = electronAPI;

		const folders = (await api.getWatchedFolders()) as WatchedFolderEntry[];

		if (folders.length === 0) {
			try {
				const backendFolders = await documentsApiService.getWatchedFolders(workspaceId);
				for (const bf of backendFolders) {
					const meta = bf.metadata as Record<string, unknown> | null;
					if (!meta?.watched || !meta.folder_path) continue;
					await api.addWatchedFolder({
						path: meta.folder_path as string,
						name: bf.name,
						rootFolderId: bf.id,
						workspaceId: bf.workspace_id,
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
	}, [workspaceId, electronAPI]);

	useEffect(() => {
		refreshWatchedIds();
	}, [refreshWatchedIds]);
	const { mutateAsync: deleteDocumentMutation } = useAtomValue(deleteDocumentMutationAtom);

	const [sidebarDocs, setSidebarDocs] = useAtom(mentionedDocumentsAtom);
	const mentionedDocKeys = useMemo(
		() => new Set(sidebarDocs.map((d) => getMentionDocKey(d))),
		[sidebarDocs]
	);

	// Folder state
	const [expandedFolderMap, setExpandedFolderMap] = useAtom(expandedFolderIdsAtom);
	const expandedIds = useMemo(
		() => new Set(expandedFolderMap[workspaceId] ?? []),
		[expandedFolderMap, workspaceId]
	);
	const toggleFolderExpand = useCallback(
		(folderId: number) => {
			setExpandedFolderMap((prev) => {
				const current = new Set(prev[workspaceId] ?? []);
				if (current.has(folderId)) current.delete(folderId);
				else current.add(folderId);
				return { ...prev, [workspaceId]: [...current] };
			});
		},
		[workspaceId, setExpandedFolderMap]
	);

	// Zero queries for tree data
	const [zeroFolders, zeroFoldersResult] = useQuery(
		queries.folders.bySpace({ workspaceId: workspaceId })
	);
	const [zeroAllDocs, zeroAllDocsResult] = useQuery(
		queries.documents.bySpace({ workspaceId: workspaceId })
	);
	const [agentCreatedDocs, setAgentCreatedDocs] = useAtom(agentCreatedDocumentsAtom);

	const treeFolders: FolderDisplay[] = useMemo(
		() =>
			(zeroFolders ?? []).map((f) => ({
				id: f.id,
				name: f.name,
				position: f.position,
				parentId: f.parentId ?? null,
				workspaceId: f.workspaceId,
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
			.filter((d) => d.workspaceId === workspaceId && !zeroIds.has(d.id))
			.map((d) => ({
				id: d.id,
				title: d.title,
				document_type: d.documentType,
				folderId: d.folderId ?? null,
				status: { state: "ready" } as { state: string; reason?: string | null },
			}));

		return [...pendingAgentDocs, ...zeroDocs];
	}, [zeroAllDocs, agentCreatedDocs, workspaceId]);

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
					workspace_id: workspaceId,
				});
				toast.success("Folder created");
				if (createFolderParentId !== null) {
					setExpandedFolderMap((prev) => {
						const current = new Set(prev[workspaceId] ?? []);
						current.add(createFolderParentId);
						return { ...prev, [workspaceId]: [...current] };
					});
				}
			} catch (e: unknown) {
				toast.error((e as Error)?.message || "Failed to create folder");
			}
		},
		[createFolderParentId, workspaceId, setExpandedFolderMap]
	);

	const handleRescanFolder = useCallback(
		async (folder: FolderDisplay) => {
			if (!electronAPI) return;

			const watchedFolders = (await electronAPI.getWatchedFolders()) as WatchedFolderEntry[];
			const matched = watchedFolders.find(
				(wf: WatchedFolderEntry) => wf.rootFolderId === folder.id
			);
			if (!matched) {
				toast.error("This folder is not being watched");
				return;
			}

			try {
				toast.info(`Re-scanning folder: ${matched.name}`);
				await uploadFolderScan({
					folderPath: matched.path,
					folderName: matched.name,
					workspaceId: workspaceId,
					excludePatterns: matched.excludePatterns ?? DEFAULT_EXCLUDE_PATTERNS,
					fileExtensions:
						matched.fileExtensions ?? Array.from(getSupportedExtensionsSet(undefined, etlService)),
					rootFolderId: folder.id,
				});
				toast.success(`Re-scan complete: ${matched.name}`);
			} catch (err) {
				toast.error((err as Error)?.message || "Failed to re-scan folder");
			}
		},
		[workspaceId, electronAPI, etlService]
	);

	const handleStopWatching = useCallback(
		async (folder: FolderDisplay) => {
			if (!electronAPI) return;

			const watchedFolders = (await electronAPI.getWatchedFolders()) as WatchedFolderEntry[];
			const matched = watchedFolders.find(
				(wf: WatchedFolderEntry) => wf.rootFolderId === folder.id
			);
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
				buildBackendUrl(`/api/v1/workspaces/${workspaceId}/export`, {
					folder_id: ctx.folder.id,
				}),
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
	}, [exportWarningContext, workspaceId, doExport]);

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
					buildBackendUrl(`/api/v1/workspaces/${workspaceId}/export`, {
						folder_id: folder.id,
					}),
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
		[workspaceId, getPendingCountInSubtree, doExport]
	);

	const handleExportDocument = useCallback(
		async (doc: DocumentNodeDoc, format: string) => {
			if (isMemoryDocument(doc)) {
				try {
					const endpoint =
						doc.document_type === "USER_MEMORY"
							? buildBackendUrl("/api/v1/users/me/memory")
							: buildBackendUrl(`/api/v1/workspaces/${workspaceId}/memory`);
					const response = await authenticatedFetch(endpoint, { method: "GET" });
					if (!response.ok) {
						const errorData = await response.json().catch(() => ({ detail: "Export failed" }));
						throw new Error(errorData.detail || "Export failed");
					}
					const data = (await response.json()) as { memory_md?: string };
					downloadTextFile(
						data.memory_md ?? "",
						doc.title.endsWith(".md") ? doc.title : `${doc.title}.md`
					);
					return;
				} catch (err) {
					console.error("Memory export failed:", err);
					toast.error(err instanceof Error ? err.message : "Export failed");
					return;
				}
			}

			const safeTitle =
				doc.title
					.replace(/[^a-zA-Z0-9 _-]/g, "_")
					.trim()
					.slice(0, 80) || "document";
			const ext = EXPORT_FILE_EXTENSIONS[format] ?? format;

			try {
				const response = await authenticatedFetch(
					buildBackendUrl(`/api/v1/workspaces/${workspaceId}/documents/${doc.id}/export`, {
						format,
					}),
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
		[workspaceId]
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
			if (isMemoryDocument(doc)) return;
			const key = getMentionDocKey({ ...doc, kind: "doc" });
			if (isMentioned) {
				setSidebarDocs((prev) => prev.filter((d) => getMentionDocKey(d) !== key));
			} else {
				setSidebarDocs((prev) => {
					if (prev.some((d) => getMentionDocKey(d) === key)) return prev;
					return [
						...prev,
						{
							id: doc.id,
							title: doc.title,
							document_type: doc.document_type as DocumentTypeEnum,
							kind: "doc",
						},
					];
				});
			}
		},
		[setSidebarDocs]
	);

	const handleToggleFolderSelect = useCallback(
		(folderId: number, selectAll: boolean) => {
			// One folder click = one folder-mention chip. The agent
			// resolves the chip to its virtual path
			// (``/documents/MyFolder/``) and walks it itself with
			// ``ls`` / ``find_documents``. We deliberately don't
			// fan out to per-doc chips anymore — the previous
			// behaviour created N chips for one click and dropped
			// nested folders entirely once selected, which the
			// agent had no way to recover.
			const folder = treeFolders.find((f) => f.id === folderId);
			if (!folder) return;
			const chip = makeFolderMention({ id: folder.id, name: folder.name });
			const chipKey = getMentionDocKey(chip);

			if (selectAll) {
				setSidebarDocs((prev) => {
					const exists = prev.some((d) => getMentionDocKey(d) === chipKey);
					return exists ? prev : [...prev, chip];
				});
			} else {
				setSidebarDocs((prev) => prev.filter((d) => getMentionDocKey(d) !== chipKey));
			}
		},
		[treeFolders, setSidebarDocs]
	);

	const treeDocumentsWithMemory = useMemo(
		() => [...MEMORY_DOCUMENTS, ...treeDocuments],
		[treeDocuments]
	);

	const openMemoryDocument = useCallback(
		(doc: DocumentNodeDoc) => {
			if (doc.document_type === "USER_MEMORY") {
				openEditorPanel({
					kind: "memory",
					memoryScope: "user",
					workspaceId: workspaceId,
					title: doc.title,
				});
				return true;
			}
			if (doc.document_type === "TEAM_MEMORY") {
				openEditorPanel({
					kind: "memory",
					memoryScope: "team",
					workspaceId: workspaceId,
					title: doc.title,
				});
				return true;
			}
			return false;
		},
		[openEditorPanel, workspaceId]
	);

	const handleResetMemoryDocument = useCallback(
		async (doc: DocumentNodeDoc) => {
			if (!isMemoryDocument(doc)) return;
			if (!window.confirm(`Reset ${doc.title.toLowerCase()}? This clears the memory document.`)) {
				return;
			}
			const endpoint =
				doc.document_type === "USER_MEMORY"
					? buildBackendUrl("/api/v1/users/me/memory/reset")
					: buildBackendUrl(`/api/v1/workspaces/${workspaceId}/memory/reset`);
			try {
				const response = await authenticatedFetch(endpoint, { method: "POST" });
				if (!response.ok) {
					const errorData = await response.json().catch(() => ({ detail: "Reset failed" }));
					throw new Error(errorData.detail || "Reset failed");
				}
				toast.success(`${doc.title} reset`);
				openMemoryDocument(doc);
			} catch (error) {
				toast.error((error as Error)?.message || `Failed to reset ${doc.title.toLowerCase()}`);
			}
		},
		[openMemoryDocument, workspaceId]
	);

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
				if (doc.kind !== "doc") return false;
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
				setSidebarDocs((prev) => prev.filter((d) => d.kind !== "doc" || d.id !== id));
				return true;
			} catch (e) {
				console.error("Error deleting document:", e);
				return false;
			}
		},
		[deleteDocumentMutation, t, setSidebarDocs]
	);

	const showCloudSkeleton =
		zeroFoldersResult.type !== "complete" || zeroAllDocsResult.type !== "complete";

	const renderDocumentTree = ({
		documents = treeDocumentsWithMemory,
		activeTypesForTree = activeTypes,
		searchQuery,
	}: {
		documents?: DocumentNodeDoc[];
		activeTypesForTree?: DocumentTypeEnum[];
		searchQuery?: string;
	} = {}) => (
		<div className="relative">
			{deletableSelectedIds.length > 0 && (
				<div className="absolute inset-x-0 top-0 z-10 flex items-center justify-center px-4 py-1.5 animate-in fade-in duration-150 pointer-events-none">
					<Button
						type="button"
						variant="destructive"
						size="sm"
						onClick={() => setBulkDeleteConfirmOpen(true)}
						className="pointer-events-auto h-auto gap-1.5 px-3 py-1 text-xs shadow-lg"
					>
						<Trash2 size={12} />
						Delete {deletableSelectedIds.length}{" "}
						{deletableSelectedIds.length === 1 ? "item" : "items"}
					</Button>
				</div>
			)}

			{showCloudSkeleton ? (
				<CloudDocumentsSkeleton />
			) : (
				<FolderTreeView
					folders={treeFolders}
					documents={documents}
					expandedIds={expandedIds}
					onToggleExpand={toggleFolderExpand}
					mentionedDocKeys={mentionedDocKeys}
					onToggleChatMention={handleToggleChatMention}
					onToggleFolderSelect={handleToggleFolderSelect}
					onRenameFolder={handleRenameFolder}
					onDeleteFolder={handleDeleteFolder}
					onMoveFolder={handleMoveFolder}
					onCreateFolder={handleCreateFolder}
					searchQuery={searchQuery}
					onPreviewDocument={(doc) => {
						if (openMemoryDocument(doc)) return;
						openEditorPanel({
							documentId: doc.id,
							workspaceId: workspaceId,
							title: doc.title,
						});
					}}
					onDeleteDocument={(doc) => handleDeleteDocument(doc.id)}
					onMoveDocument={handleMoveDocument}
					onResetDocument={handleResetMemoryDocument}
					onExportDocument={handleExportDocument}
					onVersionHistory={(doc) => setVersionDocId(doc.id)}
					activeTypes={activeTypesForTree}
					onDropIntoFolder={handleDropIntoFolder}
					onReorderFolder={handleReorderFolder}
					watchedFolderIds={watchedFolderIds}
					onRescanFolder={handleRescanFolder}
					onStopWatchingFolder={handleStopWatching}
					onExportFolder={handleExportFolder}
				/>
			)}
		</div>
	);

	if (embedded) {
		return (
			<>
				<SidebarSection
					title={t("title") || "Documents"}
					defaultOpen={true}
					contentClassName="px-0"
					persistentAction={
						<div className="flex items-center gap-1.5">
							<EmbeddedImportMenu onFolderWatched={refreshWatchedIds} />
							<EmbeddedDocumentsMenu
								typeCounts={typeCounts}
								activeTypes={activeTypes}
								onToggleType={onToggleType}
								onCreateFolder={() => handleCreateFolder(null)}
							/>
						</div>
					}
				>
					{renderDocumentTree()}
				</SidebarSection>

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
								will be permanently deleted from your workspace.
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
								{exportWarningContext?.pendingCount !== 1 ? "s are" : " is"} currently being
								processed and will be excluded from the export. Do you want to continue?
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
			</>
		);
	}

	return null;
}

// ---------------------------------------------------------------------------
// Anonymous Documents Sidebar
// ---------------------------------------------------------------------------

function AnonymousDocumentsSidebar({ embedded = false }: DocumentsSidebarProps) {
	const t = useTranslations("documents");
	const anonMode = useAnonymousMode();
	const { gate } = useLoginGate();

	const [sidebarDocs, setSidebarDocs] = useAtom(mentionedDocumentsAtom);
	const mentionedDocKeys = useMemo(
		() => new Set(sidebarDocs.map((d) => getMentionDocKey(d))),
		[sidebarDocs]
	);

	const handleToggleChatMention = useCallback(
		(doc: { id: number; title: string; document_type: string }, isMentioned: boolean) => {
			const key = getMentionDocKey({ ...doc, kind: "doc" });
			if (isMentioned) {
				setSidebarDocs((prev) => prev.filter((d) => getMentionDocKey(d) !== key));
			} else {
				setSidebarDocs((prev) => {
					if (prev.some((d) => getMentionDocKey(d) === key)) return prev;
					return [
						...prev,
						{
							id: doc.id,
							title: doc.title,
							document_type: doc.document_type as DocumentTypeEnum,
							kind: "doc",
						},
					];
				});
			}
		},
		[setSidebarDocs]
	);

	const uploadedDoc = anonMode.isAnonymous ? anonMode.uploadedDoc : null;
	const hasDoc = uploadedDoc !== null;

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

	if (embedded) {
		return (
			<SidebarSection
				title={t("title") || "Documents"}
				defaultOpen={true}
				contentClassName="px-0"
				persistentAction={
					<div className="flex items-center gap-1.5">
						<EmbeddedImportMenu gate={gate} />
						<EmbeddedDocumentsMenu
							typeCounts={hasDoc ? { FILE: 1 } : {}}
							activeTypes={[]}
							onToggleType={() => {}}
							onCreateFolder={() => gate("create folders")}
						/>
					</div>
				}
			>
				<FolderTreeView
					folders={[]}
					documents={treeDocuments}
					expandedIds={new Set()}
					onToggleExpand={() => {}}
					mentionedDocKeys={mentionedDocKeys}
					onToggleChatMention={handleToggleChatMention}
					onToggleFolderSelect={() => {}}
					onRenameFolder={() => gate("rename folders")}
					onDeleteFolder={() => gate("delete folders")}
					onMoveFolder={() => gate("organize folders")}
					onCreateFolder={() => gate("create folders")}
					onPreviewDocument={() => gate("preview documents")}
					onDeleteDocument={async () => {
						handleRemoveDoc();
						setSidebarDocs((prev) => prev.filter((d) => d.kind !== "doc" || d.id !== -1));
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
			</SidebarSection>
		);
	}

	return null;
}
