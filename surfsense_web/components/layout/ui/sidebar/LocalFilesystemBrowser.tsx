"use client";

import { ChevronDown, ChevronRight, FileText, Folder } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { DEFAULT_EXCLUDE_PATTERNS } from "@/components/sources/FolderWatchDialog";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { useElectronAPI } from "@/hooks/use-platform";
import { getSupportedExtensionsSet } from "@/lib/supported-extensions";

interface LocalFilesystemBrowserProps {
	rootPaths: string[];
	searchSpaceId: number;
	active?: boolean;
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

type MountLoadStatus = "idle" | "loading" | "complete" | "error";

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
	active = true,
	searchQuery,
	onOpenFile,
}: LocalFilesystemBrowserProps) {
	const electronAPI = useElectronAPI();
	const [rootStateMap, setRootStateMap] = useState<Record<string, RootLoadState>>({});
	const [expandedFolderKeys, setExpandedFolderKeys] = useState<Set<string>>(new Set());
	const [mountByRootKey, setMountByRootKey] = useState<Map<string, string>>(new Map());
	const [mountStatus, setMountStatus] = useState<MountLoadStatus>("idle");
	const [mountRefreshInFlight, setMountRefreshInFlight] = useState(false);
	const [reloadNonceByRoot, setReloadNonceByRoot] = useState<Record<string, number>>({});
	const lastLoadedSignatureByRootRef = useRef<Map<string, string>>(new Map());
	const hasLoadedMountsOnceRef = useRef(false);
	const hasResolvedAtLeastOneRootRef = useRef(false);
	const supportedExtensions = useMemo(() => Array.from(getSupportedExtensionsSet()), []);
	const isWindowsPlatform = electronAPI?.versions.platform === "win32";

	useEffect(() => {
		if (!active) return;
		if (!electronAPI?.listAgentFilesystemFiles) {
			for (const rootPath of rootPaths) {
				setRootStateMap((prev) => ({
					...prev,
					[rootPath]: {
						loading: false,
						error: "Desktop app update required for local mode browsing.",
						files: [],
					},
				}));
			}
			return;
		}
		const rootEntries = rootPaths.map((rootPath) => ({
			rootPath,
			rootKey: normalizeRootPathForLookup(rootPath, isWindowsPlatform),
		}));
		const activeRootKeys = new Set(rootEntries.map((entry) => entry.rootKey));
		for (const key of Array.from(lastLoadedSignatureByRootRef.current.keys())) {
			if (!activeRootKeys.has(key)) {
				lastLoadedSignatureByRootRef.current.delete(key);
			}
		}
		const rootsToReload = rootEntries.filter(({ rootKey }) => {
			const nonce = reloadNonceByRoot[rootKey] ?? 0;
			const signature = `${searchSpaceId}:${rootKey}:${nonce}`;
			return lastLoadedSignatureByRootRef.current.get(rootKey) !== signature;
		});
		if (rootsToReload.length === 0) {
			return;
		}
		for (const { rootKey } of rootsToReload) {
			const nonce = reloadNonceByRoot[rootKey] ?? 0;
			lastLoadedSignatureByRootRef.current.set(
				rootKey,
				`${searchSpaceId}:${rootKey}:${nonce}`
			);
		}
		let cancelled = false;

		for (const { rootPath } of rootsToReload) {
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
			rootsToReload.map(async ({ rootPath }) => {
				try {
					const files = (await electronAPI.listAgentFilesystemFiles({
						rootPath,
						searchSpaceId,
						excludePatterns: DEFAULT_EXCLUDE_PATTERNS,
						fileExtensions: supportedExtensions,
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
	}, [active, electronAPI, isWindowsPlatform, reloadNonceByRoot, rootPaths, searchSpaceId, supportedExtensions]);

	useEffect(() => {
		if (active) return;
		lastLoadedSignatureByRootRef.current.clear();
	}, [active]);

	useEffect(() => {
		if (!electronAPI?.startAgentFilesystemTreeWatch) return;
		if (!electronAPI?.stopAgentFilesystemTreeWatch) return;
		if (!electronAPI?.onAgentFilesystemTreeDirty) return;
		if (!active) return;
		if (rootPaths.length === 0) {
			void electronAPI.stopAgentFilesystemTreeWatch(searchSpaceId);
			return;
		}

		const unsubscribe = electronAPI.onAgentFilesystemTreeDirty((event) => {
			if ((event.searchSpaceId ?? null) !== (searchSpaceId ?? null)) {
				return;
			}
			const eventRootKey = normalizeRootPathForLookup(event.rootPath, isWindowsPlatform);
			const knownRootKeys = new Set(
				rootPaths.map((rootPath) => normalizeRootPathForLookup(rootPath, isWindowsPlatform))
			);
			if (!knownRootKeys.has(eventRootKey)) {
				setReloadNonceByRoot((prev) => {
					const next = { ...prev };
					for (const rootKey of knownRootKeys) {
						next[rootKey] = (prev[rootKey] ?? 0) + 1;
					}
					return next;
				});
				return;
			}
			setReloadNonceByRoot((prev) => ({
				...prev,
				[eventRootKey]: (prev[eventRootKey] ?? 0) + 1,
			}));
		});
		void electronAPI.startAgentFilesystemTreeWatch({
			searchSpaceId,
			rootPaths,
			excludePatterns: DEFAULT_EXCLUDE_PATTERNS,
			fileExtensions: supportedExtensions,
		});

		return () => {
			unsubscribe();
			void electronAPI.stopAgentFilesystemTreeWatch(searchSpaceId);
		};
	}, [active, electronAPI, isWindowsPlatform, rootPaths, searchSpaceId, supportedExtensions]);

	useEffect(() => {
		if (!electronAPI?.getAgentFilesystemMounts) {
			setMountStatus("error");
			setMountByRootKey(new Map());
			return;
		}
		if (rootPaths.length === 0) {
			setMountByRootKey(new Map());
			setMountStatus("complete");
			setMountRefreshInFlight(false);
			hasLoadedMountsOnceRef.current = true;
			return;
		}
		let cancelled = false;
		const isInitialMountLoad = !hasLoadedMountsOnceRef.current;
		if (isInitialMountLoad) {
			setMountStatus("loading");
		} else {
			setMountRefreshInFlight(true);
		}
		void electronAPI
			.getAgentFilesystemMounts(searchSpaceId)
			.then((mounts: LocalRootMount[]) => {
				if (cancelled) return;
				const next = new Map<string, string>();
				for (const entry of mounts) {
					const normalizedRootKey = normalizeRootPathForLookup(entry.rootPath, isWindowsPlatform);
					next.set(normalizedRootKey, entry.mount);
				}
				setMountByRootKey(next);
				setMountStatus("complete");
				hasLoadedMountsOnceRef.current = true;
			})
			.catch(() => {
				if (cancelled) return;
				if (isInitialMountLoad) {
					setMountByRootKey(new Map());
					setMountStatus("error");
				}
			})
			.finally(() => {
				if (cancelled) return;
				setMountRefreshInFlight(false);
			});
		return () => {
			cancelled = true;
		};
	}, [electronAPI, isWindowsPlatform, rootPaths, searchSpaceId]);

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

	const allRootsLoaded = rootPaths.every((rootPath) => {
		const state = rootStateMap[rootPath];
		return !!state && !state.loading;
	});
	const mountsSettled = mountStatus === "complete" || mountStatus === "error";
	if (allRootsLoaded && mountsSettled && rootPaths.length > 0) {
		hasResolvedAtLeastOneRootRef.current = true;
	}
	const showInitialLoading =
		!hasResolvedAtLeastOneRootRef.current && (!allRootsLoaded || !mountsSettled);

	if (showInitialLoading) {
		const rows = [
			{ id: "local-row-1", widthClass: "w-44" },
			{ id: "local-row-2", widthClass: "w-32" },
			{ id: "local-row-3", widthClass: "w-32" },
			{ id: "local-row-4", widthClass: "w-44" },
			{ id: "local-row-5", widthClass: "w-32" },
			{ id: "local-row-6", widthClass: "w-32" },
			{ id: "local-row-7", widthClass: "w-44" },
			{ id: "local-row-8", widthClass: "w-32" },
		];

		return (
			<div className="flex-1 min-h-0 overflow-y-auto px-2 py-2">
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

	return (
		<div className="flex-1 min-h-0 overflow-y-auto px-2 py-2">
			{treeByRoot.map(({ rootPath, rootNode, matchCount, totalCount }) => {
				const state = rootStateMap[rootPath];
				const rootKey = normalizeRootPathForLookup(rootPath, isWindowsPlatform);
				const mount = mountByRootKey.get(rootKey);
				if (!state || state.loading) {
					return (
						<div key={rootPath} className="mb-1 px-3 py-2 text-xs text-muted-foreground/80">
							<div className="flex items-center gap-2">
								<Spinner className="size-3.5" />
								<span>Loading {getFolderDisplayName(rootPath)}...</span>
							</div>
						</div>
					);
				}
				if (state.error) {
					return (
						<div key={rootPath} className="rounded-md border border-destructive/20 bg-destructive/5 p-3">
							<p className="text-sm font-medium text-destructive">Failed to load local folder</p>
							<p className="mt-1 text-xs text-muted-foreground">{state.error}</p>
						</div>
					);
				}
				const isEmpty = totalCount === 0;
				return (
					<div key={rootPath} className="mb-1">
						{mount ? renderFolder(rootNode, 0, mount) : null}
						{!mount && (mountRefreshInFlight || mountStatus === "loading") && (
							<div className="px-3 pb-2 text-xs text-muted-foreground/80">
								<div className="flex items-center gap-2">
									<Spinner className="size-3.5" />
									<span>Loading {getFolderDisplayName(rootPath)}...</span>
								</div>
							</div>
						)}
						{!mount && mountStatus === "complete" && !mountRefreshInFlight && (
							<div className="px-3 pb-2 text-xs text-muted-foreground/80">
								Unable to resolve mounted root for this folder.
							</div>
						)}
						{!mount && mountStatus === "error" && (
							<div className="px-3 pb-2 text-xs text-muted-foreground/80">
								Failed to resolve local folder mounts.
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
