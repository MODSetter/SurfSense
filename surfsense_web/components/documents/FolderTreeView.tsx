"use client";

import { useAtom } from "jotai";
import { Search } from "lucide-react";
import { useCallback, useMemo, useState } from "react";
import { DndProvider } from "react-dnd";
import { HTML5Backend } from "react-dnd-html5-backend";
import { renamingFolderIdAtom } from "@/atoms/documents/folder.atoms";
import type { DocumentTypeEnum } from "@/contracts/types/document.types";
import { getMentionDocKey } from "@/lib/chat/mention-doc-key";
import { DocumentNode, type DocumentNodeDoc } from "./DocumentNode";
import { type FolderDisplay, FolderNode } from "./FolderNode";

export type FolderSelectionState = "all" | "some" | "none";

interface FolderTreeViewProps {
	folders: FolderDisplay[];
	documents: DocumentNodeDoc[];
	expandedIds: Set<number>;
	onToggleExpand: (folderId: number) => void;
	mentionedDocKeys: Set<string>;
	onToggleChatMention: (
		doc: { id: number; title: string; document_type: string },
		isMentioned: boolean
	) => void;
	onToggleFolderSelect: (folderId: number, selectAll: boolean) => void;
	onRenameFolder: (folder: FolderDisplay, newName: string) => void;
	onDeleteFolder: (folder: FolderDisplay) => void;
	onMoveFolder: (folder: FolderDisplay) => void;
	onCreateFolder: (parentId: number | null) => void;
	onPreviewDocument: (doc: DocumentNodeDoc) => void;
	onEditDocument: (doc: DocumentNodeDoc) => void;
	onDeleteDocument: (doc: DocumentNodeDoc) => void;
	onMoveDocument: (doc: DocumentNodeDoc) => void;
	onExportDocument?: (doc: DocumentNodeDoc, format: string) => void;
	onVersionHistory?: (doc: DocumentNodeDoc) => void;
	activeTypes: DocumentTypeEnum[];
	searchQuery?: string;
	onDropIntoFolder?: (
		itemType: "folder" | "document",
		itemId: number,
		targetFolderId: number | null
	) => void;
	onReorderFolder?: (folderId: number, beforePos: string | null, afterPos: string | null) => void;
	watchedFolderIds?: Set<number>;
	onRescanFolder?: (folder: FolderDisplay) => void;
	onStopWatchingFolder?: (folder: FolderDisplay) => void;
	onExportFolder?: (folder: FolderDisplay) => void;
}

function groupBy<T>(items: T[], keyFn: (item: T) => string | number): Record<string | number, T[]> {
	const result: Record<string | number, T[]> = {};
	for (const item of items) {
		const key = keyFn(item);
		if (!result[key]) result[key] = [];
		result[key].push(item);
	}
	return result;
}

export function FolderTreeView({
	folders,
	documents,
	expandedIds,
	onToggleExpand,
	mentionedDocKeys,
	onToggleChatMention,
	onToggleFolderSelect,
	onRenameFolder,
	onDeleteFolder,
	onMoveFolder,
	onCreateFolder,
	onPreviewDocument,
	onEditDocument,
	onDeleteDocument,
	onMoveDocument,
	onExportDocument,
	onVersionHistory,
	activeTypes,
	searchQuery,
	onDropIntoFolder,
	onReorderFolder,
	watchedFolderIds,
	onRescanFolder,
	onStopWatchingFolder,
	onExportFolder,
}: FolderTreeViewProps) {
	const foldersByParent = useMemo(() => groupBy(folders, (f) => f.parentId ?? "root"), [folders]);

	const docsByFolder = useMemo(() => groupBy(documents, (d) => d.folderId ?? "root"), [documents]);

	const [openContextMenuId, setOpenContextMenuId] = useState<string | null>(null);

	const [manuallyCollapsedAiIds, setManuallyCollapsedAiIds] = useState<Set<number>>(new Set());

	// Single subscription for rename state — derived boolean passed to each FolderNode
	const [renamingFolderId, setRenamingFolderId] = useAtom(renamingFolderIdAtom);
	const handleStartRename = useCallback(
		(folderId: number) => setRenamingFolderId(folderId),
		[setRenamingFolderId]
	);
	const handleCancelRename = useCallback(() => setRenamingFolderId(null), [setRenamingFolderId]);

	const aiSortFolderLevels = useMemo(() => {
		const map = new Map<number, number>();
		for (const f of folders) {
			if (f.metadata?.ai_sort === true && typeof f.metadata?.ai_sort_level === "number") {
				map.set(f.id, f.metadata.ai_sort_level as number);
			}
		}
		return map;
	}, [folders]);

	const handleToggleExpand = useCallback(
		(folderId: number) => {
			const aiLevel = aiSortFolderLevels.get(folderId);
			if (aiLevel !== undefined && aiLevel < 4) {
				// AI-auto-expanded folder: only toggle the manual-collapse set.
				// Calling onToggleExpand would add it to expandedIds and fight auto-expand.
				setManuallyCollapsedAiIds((prev) => {
					const next = new Set(prev);
					if (next.has(folderId)) {
						next.delete(folderId);
					} else {
						next.add(folderId);
					}
					return next;
				});
				return;
			}
			onToggleExpand(folderId);
		},
		[onToggleExpand, aiSortFolderLevels]
	);

	const effectiveActiveTypes = useMemo(() => {
		if (
			activeTypes.includes("FILE" as DocumentTypeEnum) &&
			!activeTypes.includes("LOCAL_FOLDER_FILE" as DocumentTypeEnum)
		) {
			return [...activeTypes, "LOCAL_FOLDER_FILE" as DocumentTypeEnum];
		}
		return activeTypes;
	}, [activeTypes]);

	const hasDescendantMatch = useMemo(() => {
		if (effectiveActiveTypes.length === 0 && !searchQuery) return null;
		const match: Record<number, boolean> = {};

		function check(folderId: number): boolean {
			if (match[folderId] !== undefined) return match[folderId];
			const childDocs = (docsByFolder[folderId] ?? []).some(
				(d) =>
					effectiveActiveTypes.length === 0 ||
					effectiveActiveTypes.includes(d.document_type as DocumentTypeEnum)
			);
			if (childDocs) {
				match[folderId] = true;
				return true;
			}
			const childFolders = foldersByParent[folderId] ?? [];
			for (const cf of childFolders) {
				if (check(cf.id)) {
					match[folderId] = true;
					return true;
				}
			}
			match[folderId] = false;
			return false;
		}

		for (const f of folders) {
			check(f.id);
		}
		return match;
	}, [folders, docsByFolder, foldersByParent, effectiveActiveTypes, searchQuery]);

	const folderSelectionStates = useMemo(() => {
		const states: Record<number, FolderSelectionState> = {};
		const isSelectable = (d: DocumentNodeDoc) =>
			d.status?.state !== "pending" && d.status?.state !== "processing";

		function compute(folderId: number): { selected: number; total: number } {
			const directDocs = (docsByFolder[folderId] ?? []).filter(isSelectable);
			let selected = directDocs.filter((d) => mentionedDocKeys.has(getMentionDocKey(d))).length;
			let total = directDocs.length;

			for (const child of foldersByParent[folderId] ?? []) {
				const sub = compute(child.id);
				selected += sub.selected;
				total += sub.total;
			}

			if (total === 0) states[folderId] = "none";
			else if (selected === total) states[folderId] = "all";
			else if (selected > 0) states[folderId] = "some";
			else states[folderId] = "none";

			return { selected, total };
		}

		for (const f of folders) {
			if (states[f.id] === undefined) compute(f.id);
		}
		return states;
	}, [folders, docsByFolder, foldersByParent, mentionedDocKeys]);

	const folderMap = useMemo(() => {
		const map: Record<number, FolderDisplay> = {};
		for (const f of folders) map[f.id] = f;
		return map;
	}, [folders]);

	const folderProcessingStates = useMemo(() => {
		const states: Record<number, "idle" | "processing" | "failed"> = {};

		function compute(folderId: number): { hasProcessing: boolean; hasFailed: boolean } {
			const directDocs = docsByFolder[folderId] ?? [];
			let hasProcessing = directDocs.some(
				(d) => d.status?.state === "pending" || d.status?.state === "processing"
			);
			let hasFailed = directDocs.some((d) => d.status?.state === "failed");

			const folder = folderMap[folderId];
			if (folder?.metadata?.indexing_in_progress) {
				hasProcessing = true;
			}

			for (const child of foldersByParent[folderId] ?? []) {
				const sub = compute(child.id);
				hasProcessing = hasProcessing || sub.hasProcessing;
				hasFailed = hasFailed || sub.hasFailed;
			}

			if (hasProcessing) states[folderId] = "processing";
			else if (hasFailed) states[folderId] = "failed";
			else states[folderId] = "idle";

			return { hasProcessing, hasFailed };
		}

		for (const f of folders) {
			if (states[f.id] === undefined) compute(f.id);
		}
		return states;
	}, [folders, docsByFolder, foldersByParent, folderMap]);

	function renderLevel(parentId: number | null, depth: number): React.ReactNode[] {
		const key = parentId ?? "root";
		const childFolders = (foldersByParent[key] ?? []).slice().sort((a, b) => {
			const aIsDate = a.metadata?.ai_sort === true && a.metadata?.ai_sort_level === 2;
			const bIsDate = b.metadata?.ai_sort === true && b.metadata?.ai_sort_level === 2;
			if (aIsDate && bIsDate) {
				return b.name.localeCompare(a.name);
			}
			return a.position.localeCompare(b.position);
		});
		const visibleFolders = hasDescendantMatch
			? childFolders.filter((f) => hasDescendantMatch[f.id])
			: childFolders;
		const childDocs = (docsByFolder[key] ?? []).filter(
			(d) =>
				effectiveActiveTypes.length === 0 ||
				effectiveActiveTypes.includes(d.document_type as DocumentTypeEnum)
		);

		const nodes: React.ReactNode[] = [];

		if (parentId === null) {
			const processingDocs = childDocs.filter((d) => {
				const state = d.status?.state;
				return state === "pending" || state === "processing";
			});
			for (const d of processingDocs) {
				nodes.push(
					<DocumentNode
						key={`doc-${d.id}`}
						doc={d}
						depth={depth}
						isMentioned={mentionedDocKeys.has(getMentionDocKey(d))}
						onToggleChatMention={onToggleChatMention}
						onPreview={onPreviewDocument}
						onEdit={onEditDocument}
						onDelete={onDeleteDocument}
						onMove={onMoveDocument}
						onExport={onExportDocument}
						onVersionHistory={onVersionHistory}
						contextMenuOpen={openContextMenuId === `doc-${d.id}`}
						onContextMenuOpenChange={(open) => setOpenContextMenuId(open ? `doc-${d.id}` : null)}
					/>
				);
			}
		}

		for (let i = 0; i < visibleFolders.length; i++) {
			const f = visibleFolders[i];
			const siblingPositions = {
				before: i > 0 ? visibleFolders[i - 1].position : null,
				after: i < visibleFolders.length - 1 ? visibleFolders[i + 1].position : null,
			};

			const isSearchAutoExpanded = !!searchQuery && !!hasDescendantMatch?.[f.id];
			const isAiAutoExpandCandidate =
				f.metadata?.ai_sort === true &&
				typeof f.metadata?.ai_sort_level === "number" &&
				(f.metadata.ai_sort_level as number) < 4;
			const isManuallyCollapsed = manuallyCollapsedAiIds.has(f.id);
			const isExpanded = isManuallyCollapsed
				? isSearchAutoExpanded
				: expandedIds.has(f.id) || isSearchAutoExpanded || isAiAutoExpandCandidate;

			nodes.push(
				<FolderNode
					key={`folder-${f.id}`}
					folder={f}
					depth={depth}
					isExpanded={isExpanded}
					isRenaming={renamingFolderId === f.id}
					selectionState={folderSelectionStates[f.id] ?? "none"}
					processingState={folderProcessingStates[f.id] ?? "idle"}
					onToggleSelect={onToggleFolderSelect}
					onToggleExpand={handleToggleExpand}
					onRename={onRenameFolder}
					onStartRename={handleStartRename}
					onCancelRename={handleCancelRename}
					onDelete={onDeleteFolder}
					onMove={onMoveFolder}
					onCreateSubfolder={onCreateFolder}
					onDropIntoFolder={onDropIntoFolder}
					onReorderFolder={onReorderFolder}
					siblingPositions={siblingPositions}
					contextMenuOpen={openContextMenuId === `folder-${f.id}`}
					onContextMenuOpenChange={(open) => setOpenContextMenuId(open ? `folder-${f.id}` : null)}
					isWatched={watchedFolderIds?.has(f.id)}
					onRescan={onRescanFolder}
					onStopWatching={onStopWatchingFolder}
					onExportFolder={onExportFolder}
				/>
			);

			if (isExpanded) {
				nodes.push(...renderLevel(f.id, depth + 1));
			}
		}

		const remainingDocs =
			parentId === null
				? childDocs.filter((d) => {
						const state = d.status?.state;
						return state !== "pending" && state !== "processing";
					})
				: childDocs;

		for (const d of remainingDocs) {
			nodes.push(
				<DocumentNode
					key={`doc-${d.id}`}
					doc={d}
					depth={depth}
					isMentioned={mentionedDocKeys.has(getMentionDocKey(d))}
					onToggleChatMention={onToggleChatMention}
					onPreview={onPreviewDocument}
					onEdit={onEditDocument}
					onDelete={onDeleteDocument}
					onMove={onMoveDocument}
					onExport={onExportDocument}
					onVersionHistory={onVersionHistory}
					contextMenuOpen={openContextMenuId === `doc-${d.id}`}
					onContextMenuOpenChange={(open) => setOpenContextMenuId(open ? `doc-${d.id}` : null)}
				/>
			);
		}

		return nodes;
	}

	const treeNodes = renderLevel(null, 0);

	if (treeNodes.length === 0 && folders.length === 0 && documents.length === 0) {
		return (
			<div className="flex flex-1 flex-col items-center justify-center gap-1 px-4 py-12 text-muted-foreground select-none">
				<p className="text-sm font-medium">No documents found</p>
				<p className="text-xs text-muted-foreground/70">
					Use the upload button or connect a source above
				</p>
			</div>
		);
	}

	if (treeNodes.length === 0 && (effectiveActiveTypes.length > 0 || searchQuery)) {
		return (
			<div className="flex flex-1 flex-col items-center justify-center gap-3 px-4 py-12 text-muted-foreground">
				<Search className="h-10 w-10" />
				<p className="text-sm text-muted-foreground">No matching documents</p>
				<p className="text-xs text-muted-foreground/70 mt-1">Try a different search term</p>
			</div>
		);
	}

	return (
		<DndProvider backend={HTML5Backend}>
			<div className="flex-1 min-h-0 overflow-y-auto px-2 py-1">{treeNodes}</div>
		</DndProvider>
	);
}
