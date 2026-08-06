import type { DocumentTypeEnum } from "@/contracts/types/document.types";
import { matchText, type TextMatch } from "./document-search";
import type { DocumentNodeDoc, FolderDisplay } from "./document-tree-types";

export type DocumentsEmptyReason =
	| { kind: "loading" }
	| { kind: "workspace_empty" }
	| { kind: "no_search_results"; query: string }
	| { kind: "no_filter_results" };

export type DocumentSearchHit =
	| {
			kind: "document";
			document: DocumentNodeDoc;
			match: TextMatch;
			path: string[];
	  }
	| {
			kind: "folder";
			folder: FolderDisplay;
			match: TextMatch;
			path: string[];
	  };

export type DocumentsViewModel =
	| { mode: "empty"; reason: DocumentsEmptyReason }
	| { mode: "browse"; folders: FolderDisplay[]; documents: DocumentNodeDoc[] }
	| { mode: "search"; hits: DocumentSearchHit[]; query: string };

interface BuildDocumentsViewModelInput {
	folders: FolderDisplay[];
	documents: DocumentNodeDoc[];
	pinnedDocuments?: DocumentNodeDoc[];
	query: string;
	activeTypes: DocumentTypeEnum[];
	isLoading?: boolean;
}

function effectiveDocumentTypes(activeTypes: DocumentTypeEnum[]): Set<string> {
	const types = new Set<string>(activeTypes);
	if (types.has("FILE")) types.add("LOCAL_FOLDER_FILE");
	return types;
}

function documentOrder(document: DocumentNodeDoc) {
	if (document.document_type === "USER_MEMORY") return 0;
	if (document.document_type === "TEAM_MEMORY") return 1;
	return 2;
}

function compareDocuments(left: DocumentNodeDoc, right: DocumentNodeDoc) {
	return (
		documentOrder(left) - documentOrder(right) ||
		right.createdAt - left.createdAt ||
		right.id - left.id
	);
}

function buildFolderPaths(folders: FolderDisplay[]): Map<number, string[]> {
	const folderById = new Map(folders.map((folder) => [folder.id, folder]));
	const paths = new Map<number, string[]>();

	function getPath(folderId: number, visiting = new Set<number>()): string[] {
		const cached = paths.get(folderId);
		if (cached) return cached;
		if (visiting.has(folderId)) return [];

		const folder = folderById.get(folderId);
		if (!folder) return [];

		visiting.add(folderId);
		const path =
			folder.parentId === null
				? []
				: [...getPath(folder.parentId, visiting), folderById.get(folder.parentId)?.name].filter(
						(name): name is string => Boolean(name)
					);
		visiting.delete(folderId);
		paths.set(folderId, path);
		return path;
	}

	for (const folder of folders) getPath(folder.id);
	return paths;
}

function foldersContainingDocuments(
	folders: FolderDisplay[],
	documents: DocumentNodeDoc[]
): FolderDisplay[] {
	const folderById = new Map(folders.map((folder) => [folder.id, folder]));
	const visibleFolderIds = new Set<number>();

	for (const document of documents) {
		let folderId = document.folderId;
		while (folderId !== null && !visibleFolderIds.has(folderId)) {
			visibleFolderIds.add(folderId);
			folderId = folderById.get(folderId)?.parentId ?? null;
		}
	}

	return folders.filter((folder) => visibleFolderIds.has(folder.id));
}

export function buildDocumentsViewModel({
	folders,
	documents,
	pinnedDocuments = [],
	query,
	activeTypes,
	isLoading = false,
}: BuildDocumentsViewModelInput): DocumentsViewModel {
	if (isLoading) return { mode: "empty", reason: { kind: "loading" } };

	const trimmedQuery = query.trim();
	const types = effectiveDocumentTypes(activeTypes);
	const allDocuments = [...pinnedDocuments, ...documents];
	const filteredDocuments = (
		types.size === 0
			? allDocuments.slice()
			: allDocuments.filter((document) => types.has(document.document_type))
	).sort(compareDocuments);

	if (allDocuments.length === 0 && folders.length === 0) {
		return { mode: "empty", reason: { kind: "workspace_empty" } };
	}

	if (activeTypes.length > 0 && filteredDocuments.length === 0) {
		return { mode: "empty", reason: { kind: "no_filter_results" } };
	}

	const visibleFolders =
		activeTypes.length === 0
			? folders
			: foldersContainingDocuments(folders, filteredDocuments);

	if (!trimmedQuery) {
		return {
			mode: "browse",
			folders: visibleFolders,
			documents: filteredDocuments,
		};
	}

	const folderPaths = buildFolderPaths(folders);
	const folderById = new Map(folders.map((folder) => [folder.id, folder]));
	const hits: DocumentSearchHit[] = [];

	for (const document of filteredDocuments) {
		const match = matchText(trimmedQuery, document.title);
		if (!match) continue;
		hits.push({
			kind: "document",
			document,
			match,
			path:
				document.folderId === null
					? []
					: [
							...(folderPaths.get(document.folderId) ?? []),
							folderById.get(document.folderId)?.name,
						].filter((name): name is string => Boolean(name)),
		});
	}

	for (const folder of visibleFolders) {
		const match = matchText(trimmedQuery, folder.name);
		if (!match) continue;
		hits.push({
			kind: "folder",
			folder,
			match,
			path: folderPaths.get(folder.id) ?? [],
		});
	}

	if (hits.length === 0) {
		return {
			mode: "empty",
			reason: { kind: "no_search_results", query: trimmedQuery },
		};
	}

	hits.sort(
		(left, right) =>
			right.match.score - left.match.score ||
			(left.kind === right.kind ? 0 : left.kind === "document" ? -1 : 1) ||
			(left.kind === "document" ? left.document.title : left.folder.name).localeCompare(
				right.kind === "document" ? right.document.title : right.folder.name
			)
	);

	return { mode: "search", hits, query: trimmedQuery };
}
