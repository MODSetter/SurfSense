"use client";

import { useAtom } from "jotai";
import { TreePine } from "lucide-react";
import { useCallback, useMemo } from "react";
import { DndProvider } from "react-dnd";
import { HTML5Backend } from "react-dnd-html5-backend";
import { renamingFolderIdAtom } from "@/atoms/documents/folder.atoms";
import type { DocumentTypeEnum } from "@/contracts/types/document.types";
import { DocumentNode, type DocumentNodeDoc } from "./DocumentNode";
import { type FolderDisplay, FolderNode } from "./FolderNode";

interface FolderTreeViewProps {
	folders: FolderDisplay[];
	documents: DocumentNodeDoc[];
	expandedIds: Set<number>;
	onToggleExpand: (folderId: number) => void;
	mentionedDocIds: Set<number>;
	onToggleChatMention: (
		doc: { id: number; title: string; document_type: string },
		isMentioned: boolean
	) => void;
	onRenameFolder: (folder: FolderDisplay, newName: string) => void;
	onDeleteFolder: (folder: FolderDisplay) => void;
	onMoveFolder: (folder: FolderDisplay) => void;
	onCreateFolder: (parentId: number | null) => void;
	onPreviewDocument: (doc: DocumentNodeDoc) => void;
	onEditDocument: (doc: DocumentNodeDoc) => void;
	onDeleteDocument: (doc: DocumentNodeDoc) => void;
	onMoveDocument: (doc: DocumentNodeDoc) => void;
	activeTypes: DocumentTypeEnum[];
	onDropIntoFolder?: (
		itemType: "folder" | "document",
		itemId: number,
		targetFolderId: number | null
	) => void;
	onReorderFolder?: (folderId: number, beforePos: string | null, afterPos: string | null) => void;
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
	mentionedDocIds,
	onToggleChatMention,
	onRenameFolder,
	onDeleteFolder,
	onMoveFolder,
	onCreateFolder,
	onPreviewDocument,
	onEditDocument,
	onDeleteDocument,
	onMoveDocument,
	activeTypes,
	onDropIntoFolder,
	onReorderFolder,
}: FolderTreeViewProps) {
	const foldersByParent = useMemo(() => groupBy(folders, (f) => f.parentId ?? "root"), [folders]);

	const docsByFolder = useMemo(() => groupBy(documents, (d) => d.folderId ?? "root"), [documents]);

	const folderChildCounts = useMemo(() => {
		const counts: Record<number, number> = {};
		for (const f of folders) {
			const children = foldersByParent[f.id] ?? [];
			const docs = docsByFolder[f.id] ?? [];
			counts[f.id] = children.length + docs.length;
		}
		return counts;
	}, [folders, foldersByParent, docsByFolder]);

	// Single subscription for rename state — derived boolean passed to each FolderNode
	const [renamingFolderId, setRenamingFolderId] = useAtom(renamingFolderIdAtom);
	const handleStartRename = useCallback(
		(folderId: number) => setRenamingFolderId(folderId),
		[setRenamingFolderId]
	);
	const handleCancelRename = useCallback(() => setRenamingFolderId(null), [setRenamingFolderId]);

	const hasDescendantMatch = useMemo(() => {
		if (activeTypes.length === 0) return null;
		const match: Record<number, boolean> = {};

		function check(folderId: number): boolean {
			if (match[folderId] !== undefined) return match[folderId];
			const childDocs = (docsByFolder[folderId] ?? []).some((d) =>
				activeTypes.includes(d.document_type as DocumentTypeEnum)
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
	}, [folders, docsByFolder, foldersByParent, activeTypes]);

	function renderLevel(parentId: number | null, depth: number): React.ReactNode[] {
		const key = parentId ?? "root";
		const childFolders = (foldersByParent[key] ?? [])
			.slice()
			.sort((a, b) => a.position.localeCompare(b.position));
		const visibleFolders = hasDescendantMatch
			? childFolders.filter((f) => hasDescendantMatch[f.id])
			: childFolders;
		const childDocs = (docsByFolder[key] ?? []).filter(
			(d) => activeTypes.length === 0 || activeTypes.includes(d.document_type as DocumentTypeEnum)
		);

		const nodes: React.ReactNode[] = [];

		for (let i = 0; i < visibleFolders.length; i++) {
			const f = visibleFolders[i];
			const siblingPositions = {
				before: i > 0 ? visibleFolders[i - 1].position : null,
				after: i < visibleFolders.length - 1 ? visibleFolders[i + 1].position : null,
			};

			nodes.push(
				<FolderNode
					key={`folder-${f.id}`}
					folder={f}
					depth={depth}
					isExpanded={expandedIds.has(f.id)}
					isRenaming={renamingFolderId === f.id}
					childCount={folderChildCounts[f.id] ?? 0}
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
				/>
			);

			if (expandedIds.has(f.id)) {
				nodes.push(...renderLevel(f.id, depth + 1));
			}
		}

		for (const d of childDocs) {
			nodes.push(
				<DocumentNode
					key={`doc-${d.id}`}
					doc={d}
					depth={depth}
					isMentioned={mentionedDocIds.has(d.id)}
					onToggleChatMention={onToggleChatMention}
					onPreview={onPreviewDocument}
					onEdit={onEditDocument}
					onDelete={onDeleteDocument}
					onMove={onMoveDocument}
				/>
			);
		}

		return nodes;
	}

	const treeNodes = renderLevel(null, 0);

	if (treeNodes.length === 0 && folders.length === 0 && documents.length === 0) {
		return (
			<div className="flex flex-1 flex-col items-center justify-center gap-3 px-4 py-12 text-muted-foreground">
				<TreePine className="h-10 w-10" />
				<p className="text-sm">No documents yet</p>
			</div>
		);
	}

	if (treeNodes.length === 0 && activeTypes.length > 0) {
		return (
			<div className="flex flex-1 flex-col items-center justify-center gap-3 px-4 py-12 text-muted-foreground">
				<TreePine className="h-10 w-10" />
				<p className="text-sm">No matching documents</p>
			</div>
		);
	}

	return (
		<DndProvider backend={HTML5Backend}>
			<div className="flex-1 min-h-0 overflow-y-auto px-2 py-1">{treeNodes}</div>
		</DndProvider>
	);
}
