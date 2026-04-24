"use client";

import { ChevronDown, ChevronRight, FileText, Folder } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { DEFAULT_EXCLUDE_PATTERNS } from "@/components/sources/FolderWatchDialog";
import { Spinner } from "@/components/ui/spinner";
import { useElectronAPI } from "@/hooks/use-platform";
import { getSupportedExtensionsSet } from "@/lib/supported-extensions";

interface LocalFilesystemBrowserProps {
	rootPaths: string[];
	searchSpaceId: number;
	searchQuery?: string;
	onOpenFile: (fullPath: string) => void;
}

interface LocalFolderFileEntry {
	relativePath: string;
	fullPath: string;
	size: number;
	mtimeMs: number;
}

type RootLoadState = {
	loading: boolean;
	error: string | null;
	files: LocalFolderFileEntry[];
};

interface LocalFolderNode {
	key: string;
	name: string;
	folders: Map<string, LocalFolderNode>;
	files: LocalFolderFileEntry[];
}

type LocalRootMount = {
	mount: string;
	rootPath: string;
};

const getFolderDisplayName = (rootPath: string): string =>
	rootPath.split(/[\\/]/).at(-1) || rootPath;

function createFolderNode(key: string, name: string): LocalFolderNode {
	return {
		key,
		name,
		folders: new Map(),
		files: [],
	};
}

function getFileName(pathValue: string): string {
	return pathValue.split(/[\\/]/).at(-1) || pathValue;
}

function toVirtualPath(relativePath: string): string {
	const normalized = relativePath.replace(/\\/g, "/").replace(/^\/+/, "");
	return `/${normalized}`;
}

function normalizeRootPathForLookup(rootPath: string, isWindows: boolean): string {
	const normalized = rootPath.replace(/\\/g, "/").replace(/\/+$/, "");
	return isWindows ? normalized.toLowerCase() : normalized;
}

function toMountedVirtualPath(mount: string, relativePath: string): string {
	return `/${mount}${toVirtualPath(relativePath)}`;
}

export function LocalFilesystemBrowser({
	rootPaths,
	searchSpaceId,
	searchQuery,
	onOpenFile,
}: LocalFilesystemBrowserProps) {
	const electronAPI = useElectronAPI();
	const [rootStateMap, setRootStateMap] = useState<Record<string, RootLoadState>>({});
	const [expandedFolderKeys, setExpandedFolderKeys] = useState<Set<string>>(new Set());
	const [mountByRootKey, setMountByRootKey] = useState<Map<string, string>>(new Map());
	const supportedExtensions = useMemo(() => Array.from(getSupportedExtensionsSet()), []);
	const isWindowsPlatform = electronAPI?.versions.platform === "win32";

	useEffect(() => {
		if (!electronAPI?.listFolderFiles) return;
		let cancelled = false;

		for (const rootPath of rootPaths) {
			setRootStateMap((prev) => ({
				...prev,
				[rootPath]: {
					loading: true,
					error: null,
					files: prev[rootPath]?.files ?? [],
				},
			}));
		}

		void Promise.all(
			rootPaths.map(async (rootPath) => {
				try {
					const files = (await electronAPI.listFolderFiles({
						path: rootPath,
						name: getFolderDisplayName(rootPath),
						excludePatterns: DEFAULT_EXCLUDE_PATTERNS,
						fileExtensions: supportedExtensions,
						rootFolderId: null,
						searchSpaceId,
						active: true,
					})) as LocalFolderFileEntry[];
					if (cancelled) return;
					setRootStateMap((prev) => ({
						...prev,
						[rootPath]: {
							loading: false,
							error: null,
							files,
						},
					}));
				} catch (error) {
					if (cancelled) return;
					setRootStateMap((prev) => ({
						...prev,
						[rootPath]: {
							loading: false,
							error: error instanceof Error ? error.message : "Failed to read folder",
							files: [],
						},
					}));
				}
			})
		);

		return () => {
			cancelled = true;
		};
	}, [electronAPI, rootPaths, searchSpaceId, supportedExtensions]);

	useEffect(() => {
		if (!electronAPI?.getAgentFilesystemMounts) {
			setMountByRootKey(new Map());
			return;
		}
		let cancelled = false;
		void electronAPI
			.getAgentFilesystemMounts()
			.then((mounts: LocalRootMount[]) => {
				if (cancelled) return;
				const next = new Map<string, string>();
				for (const entry of mounts) {
					next.set(normalizeRootPathForLookup(entry.rootPath, isWindowsPlatform), entry.mount);
				}
				setMountByRootKey(next);
			})
			.catch(() => {
				if (cancelled) return;
				setMountByRootKey(new Map());
			});
		return () => {
			cancelled = true;
		};
	}, [electronAPI, isWindowsPlatform, rootPaths]);

	const treeByRoot = useMemo(() => {
		const query = searchQuery?.trim().toLowerCase() ?? "";
		const hasQuery = query.length > 0;

		return rootPaths.map((rootPath) => {
			const rootNode = createFolderNode(rootPath, getFolderDisplayName(rootPath));
			const allFiles = rootStateMap[rootPath]?.files ?? [];
			const files = hasQuery
				? allFiles.filter((file) => {
						const relativePath = file.relativePath.toLowerCase();
						const fileName = getFileName(file.relativePath).toLowerCase();
						return relativePath.includes(query) || fileName.includes(query);
					})
				: allFiles;
			for (const file of files) {
				const parts = file.relativePath.split(/[\\/]/).filter(Boolean);
				let cursor = rootNode;
				for (let i = 0; i < parts.length - 1; i++) {
					const part = parts[i];
					const folderKey = `${cursor.key}/${part}`;
					if (!cursor.folders.has(part)) {
						cursor.folders.set(part, createFolderNode(folderKey, part));
					}
					cursor = cursor.folders.get(part) as LocalFolderNode;
				}
				cursor.files.push(file);
			}
			return { rootPath, rootNode, matchCount: files.length, totalCount: allFiles.length };
		});
	}, [rootPaths, rootStateMap, searchQuery]);

	const toggleFolder = useCallback((folderKey: string) => {
		setExpandedFolderKeys((prev) => {
			const next = new Set(prev);
			if (next.has(folderKey)) {
				next.delete(folderKey);
			} else {
				next.add(folderKey);
			}
			return next;
		});
	}, []);

	const renderFolder = useCallback(
		(folder: LocalFolderNode, depth: number, mount: string) => {
			const isExpanded = expandedFolderKeys.has(folder.key);
			const childFolders = Array.from(folder.folders.values()).sort((a, b) =>
				a.name.localeCompare(b.name)
			);
			const files = [...folder.files].sort((a, b) => a.relativePath.localeCompare(b.relativePath));
			return (
				<div key={folder.key} className="select-none">
					<button
						type="button"
						onClick={() => toggleFolder(folder.key)}
						className="flex h-8 w-full items-center gap-1.5 rounded-md px-2 text-left text-sm transition-colors hover:bg-muted/60"
						style={{ paddingInlineStart: `${depth * 12 + 8}px` }}
						draggable={false}
					>
						{isExpanded ? (
							<ChevronDown className="size-3.5 shrink-0 text-muted-foreground" />
						) : (
							<ChevronRight className="size-3.5 shrink-0 text-muted-foreground" />
						)}
						<Folder className="size-3.5 shrink-0 text-muted-foreground" />
						<span className="truncate">{folder.name}</span>
					</button>
					{isExpanded && (
						<>
							{childFolders.map((childFolder) => renderFolder(childFolder, depth + 1, mount))}
							{files.map((file) => (
								<button
									key={file.fullPath}
									type="button"
									onClick={() => onOpenFile(toMountedVirtualPath(mount, file.relativePath))}
									className="flex h-8 w-full items-center gap-1.5 rounded-md px-2 text-left text-sm transition-colors hover:bg-muted/60"
									style={{ paddingInlineStart: `${(depth + 1) * 12 + 22}px` }}
									title={file.fullPath}
									draggable={false}
								>
									<FileText className="size-3.5 shrink-0 text-muted-foreground" />
									<span className="truncate">{getFileName(file.relativePath)}</span>
								</button>
							))}
						</>
					)}
				</div>
			);
		},
		[expandedFolderKeys, onOpenFile, toggleFolder]
	);

	if (rootPaths.length === 0) {
		return (
			<div className="flex flex-1 flex-col items-center justify-center gap-2 px-4 py-10 text-center text-muted-foreground">
				<p className="text-sm font-medium">No local folder selected</p>
				<p className="text-xs text-muted-foreground/80">
					Add a local folder above to browse files in desktop mode.
				</p>
			</div>
		);
	}

	return (
		<div className="flex-1 min-h-0 overflow-y-auto px-2 py-2">
			{treeByRoot.map(({ rootPath, rootNode, matchCount, totalCount }) => {
				const state = rootStateMap[rootPath];
				const rootKey = normalizeRootPathForLookup(rootPath, isWindowsPlatform);
				const mount = mountByRootKey.get(rootKey);
				if (!state || state.loading) {
					return (
						<div
							key={rootPath}
							className="flex h-16 items-center gap-2 px-3 text-sm text-muted-foreground"
						>
							<Spinner size="sm" />
							<span>Loading {getFolderDisplayName(rootPath)}...</span>
						</div>
					);
				}
				if (state.error) {
					return (
						<div
							key={rootPath}
							className="rounded-md border border-destructive/20 bg-destructive/5 p-3"
						>
							<p className="text-sm font-medium text-destructive">Failed to load local folder</p>
							<p className="mt-1 text-xs text-muted-foreground">{state.error}</p>
						</div>
					);
				}
				const isEmpty = totalCount === 0;
				return (
					<div key={rootPath} className="mb-1">
						{mount ? renderFolder(rootNode, 0, mount) : null}
						{!mount && (
							<div className="px-3 pb-2 text-xs text-muted-foreground/80">
								Unable to resolve mounted root for this folder.
							</div>
						)}
						{isEmpty && (
							<div className="px-3 pb-2 text-xs text-muted-foreground/80">
								No supported files found in this folder.
							</div>
						)}
						{!isEmpty && matchCount === 0 && searchQuery && (
							<div className="px-3 pb-2 text-xs text-muted-foreground/80">
								No matching files in this folder.
							</div>
						)}
					</div>
				);
			})}
		</div>
	);
}
