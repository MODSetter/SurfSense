"use client";

import { useAtom } from "jotai";
import { useCallback, useMemo, useState } from "react";
import { DndProvider } from "react-dnd";
import { HTML5Backend } from "react-dnd-html5-backend";
import { renamingFolderIdAtom } from "@/atoms/documents/folder.atoms";
import { getMentionDocKey } from "@/lib/chat/mention-doc-key";
import type {
	DocumentNodeDoc,
	FolderDisplay,
	FolderSelectionState,
} from "@/lib/documents/document-tree-types";
import { DocumentNode } from "./DocumentNode";
import { FolderNode } from "./FolderNode";

export interface FolderTreeViewProps {
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
	onDeleteDocument: (doc: DocumentNodeDoc) => void;
	onMoveDocument: (doc: DocumentNodeDoc) => void;
	onResetDocument?: (doc: DocumentNodeDoc) => void;
	onExportDocument?: (doc: DocumentNodeDoc, format: string) => void;
	onVersionHistory?: (doc: DocumentNodeDoc) => void;
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
	onDeleteDocument,
	onMoveDocument,
	onResetDocument,
	onExportDocument,
	onVersionHistory,
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

	// Single subscription for rename state — derived boolean passed to each FolderNode
	const [renamingFolderId, setRenamingFolderId] = useAtom(renamingFolderIdAtom);
	const handleStartRename = useCallback(
		(folderId: number) => setRenamingFolderId(folderId),
		[setRenamingFolderId]
	);
	const handleCancelRename = useCallback(() => setRenamingFolderId(null), [setRenamingFolderId]);

	const folderSelectionStates = useMemo(() => {
		// One folder = one chip. The checkbox now reflects whether the
		// folder itself is mentioned, not whether every nested doc is —
		// that reverses the old subtree-fanout semantics in
		// ``DocumentRightPanel.handleToggleFolderSelect``. We keep the
		// ``"all" | "some" | "none"`` tri-state on the type so the
		// existing ``FolderNode`` UI (which renders an indeterminate
		// glyph for ``"some"``) stays compatible, but only ``"all"``
		// and ``"none"`` are used in practice.
		const states: Record<number, FolderSelectionState> = {};
		for (const f of folders) {
			const folderMentionKey = getMentionDocKey({
				id: f.id,
				kind: "folder",
			});
			states[f.id] = mentionedDocKeys.has(folderMentionKey) ? "all" : "none";
		}
		return states;
	}, [folders, mentionedDocKeys]);

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

	const renderDocumentNode = useCallback(
		(d: DocumentNodeDoc, depth: number) => {
			const isMemoryDocument =
				d.document_type === "USER_MEMORY" || d.document_type === "TEAM_MEMORY";
			return (
				<DocumentNode
					key={`doc-${d.id}`}
					doc={d}
					depth={depth}
					isMentioned={!isMemoryDocument && mentionedDocKeys.has(getMentionDocKey(d))}
					onToggleChatMention={onToggleChatMention}
					onPreview={onPreviewDocument}
					onDelete={onDeleteDocument}
					onMove={onMoveDocument}
					onReset={onResetDocument}
					onExport={onExportDocument}
					onVersionHistory={isMemoryDocument ? undefined : onVersionHistory}
					canDelete={!isMemoryDocument}
					canMove={!isMemoryDocument}
					canMention={!isMemoryDocument}
					contextMenuOpen={openContextMenuId === `doc-${d.id}`}
					onContextMenuOpenChange={(open) => setOpenContextMenuId(open ? `doc-${d.id}` : null)}
				/>
			);
		},
		[
			mentionedDocKeys,
			onDeleteDocument,
			onExportDocument,
			onMoveDocument,
			onPreviewDocument,
			onResetDocument,
			onToggleChatMention,
			onVersionHistory,
			openContextMenuId,
		]
	);

	function renderLevel(parentId: number | null, depth: number): React.ReactNode[] {
		const key = parentId ?? "root";
		const childFolders = (foldersByParent[key] ?? [])
			.slice()
			.sort((a, b) => a.position.localeCompare(b.position));
		const childDocs = docsByFolder[key] ?? [];

		const nodes: React.ReactNode[] = [];

		for (let i = 0; i < childFolders.length; i++) {
			const f = childFolders[i];
			const siblingPositions = {
				before: i > 0 ? childFolders[i - 1].position : null,
				after: i < childFolders.length - 1 ? childFolders[i + 1].position : null,
			};

			const isExpanded = expandedIds.has(f.id);

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
					onToggleExpand={onToggleExpand}
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

		for (const d of childDocs) {
			nodes.push(renderDocumentNode(d, depth));
		}

		return nodes;
	}

	const treeNodes = renderLevel(null, 0);

	return (
		<DndProvider backend={HTML5Backend}>
			<div className="px-2 py-1">{treeNodes}</div>
		</DndProvider>
	);
}
