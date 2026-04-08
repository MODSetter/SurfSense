"use client";

import {
	ChevronDown,
	ChevronRight,
	File,
	FileSpreadsheet,
	FileText,
	FolderClosed,
	FolderOpen,
	HardDrive,
	Image,
	Presentation,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Checkbox } from "@/components/ui/checkbox";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Spinner } from "@/components/ui/spinner";
import { cn } from "@/lib/utils";

export interface DriveItem {
	id: string;
	name: string;
	mimeType: string;
	isFolder: boolean;
	parents?: string[];
	size?: number;
	iconLink?: string | null;
}

interface ItemTreeNode {
	item: DriveItem;
	children: DriveItem[] | null;
	isExpanded: boolean;
	isLoading: boolean;
}

export interface SelectedFolder {
	id: string;
	name: string;
}

interface DriveFolderTreeProps {
	fetchItems: (parentId?: string) => Promise<{ items: DriveItem[] }>;
	selectedFolders: SelectedFolder[];
	onSelectFolders: (folders: SelectedFolder[]) => void;
	selectedFiles?: SelectedFolder[];
	onSelectFiles?: (files: SelectedFolder[]) => void;
	onAuthError?: (message: string) => void;
	rootLabel?: string;
	providerName?: string;
}

function getFileIcon(mimeType?: string, className: string = "h-4 w-4") {
	const type = mimeType ?? "";
	if (type.includes("spreadsheet") || type.includes("excel")) {
		return <FileSpreadsheet className={`${className} text-muted-foreground`} />;
	}
	if (type.includes("presentation") || type.includes("powerpoint")) {
		return <Presentation className={`${className} text-muted-foreground`} />;
	}
	if (type.includes("document") || type.includes("word") || type.includes("text")) {
		return <FileText className={`${className} text-muted-foreground`} />;
	}
	if (type.includes("image")) {
		return <Image className={`${className} text-muted-foreground`} />;
	}
	return <File className={`${className} text-muted-foreground`} />;
}

export function DriveFolderTree({
	fetchItems,
	selectedFolders,
	onSelectFolders,
	selectedFiles = [],
	onSelectFiles = () => {},
	onAuthError,
	rootLabel = "My Drive",
	providerName = "Drive",
}: DriveFolderTreeProps) {
	const [itemStates, setItemStates] = useState<Map<string, ItemTreeNode>>(new Map());
	const [rootItems, setRootItems] = useState<DriveItem[]>([]);
	const [isLoadingRoot, setIsLoadingRoot] = useState(true);
	const [rootError, setRootError] = useState<Error | null>(null);

	useEffect(() => {
		let cancelled = false;
		setIsLoadingRoot(true);
		setRootError(null);

		fetchItems()
			.then((data) => {
				if (!cancelled) {
					setRootItems(data.items || []);
					setIsLoadingRoot(false);
				}
			})
			.catch((err) => {
				if (!cancelled) {
					const error = err instanceof Error ? err : new Error(String(err));
					setRootError(error);
					setIsLoadingRoot(false);
					if (onAuthError) {
						const msg = error.message;
						if (
							msg.toLowerCase().includes("authentication expired") ||
							msg.toLowerCase().includes("re-authenticate")
						) {
							onAuthError(msg);
						}
					}
				}
			});

		return () => {
			cancelled = true;
		};
	}, [fetchItems, onAuthError]);

	const isFolderSelected = (folderId: string): boolean => {
		return selectedFolders.some((f) => f.id === folderId);
	};

	const isFileSelected = (fileId: string): boolean => {
		return selectedFiles.some((f) => f.id === fileId);
	};

	const toggleFolderSelection = (folderId: string, folderName: string) => {
		if (isFolderSelected(folderId)) {
			onSelectFolders(selectedFolders.filter((f) => f.id !== folderId));
		} else {
			onSelectFolders([...selectedFolders, { id: folderId, name: folderName }]);
		}
	};

	const toggleFileSelection = (fileId: string, fileName: string) => {
		if (isFileSelected(fileId)) {
			onSelectFiles(selectedFiles.filter((f) => f.id !== fileId));
		} else {
			onSelectFiles([...selectedFiles, { id: fileId, name: fileName }]);
		}
	};

	const findItem = useCallback(
		(itemId: string): DriveItem | undefined => {
			const state = itemStates.get(itemId);
			if (state?.item) return state.item;

			const rootItem = rootItems.find((item) => item.id === itemId);
			if (rootItem) return rootItem;

			for (const [, nodeState] of itemStates) {
				if (nodeState.children) {
					const found = nodeState.children.find((child) => child.id === itemId);
					if (found) return found;
				}
			}

			return undefined;
		},
		[itemStates, rootItems]
	);

	const loadFolderContents = useCallback(
		async (folderId: string) => {
			try {
				setItemStates((prev) => {
					const newMap = new Map(prev);
					const existing = newMap.get(folderId);
					if (existing) {
						newMap.set(folderId, { ...existing, isLoading: true });
					} else {
						const item = findItem(folderId);
						if (item) {
							newMap.set(folderId, {
								item,
								children: null,
								isExpanded: false,
								isLoading: true,
							});
						}
					}
					return newMap;
				});

				const data = await fetchItems(folderId);
				const items = data.items || [];

				setItemStates((prev) => {
					const newMap = new Map(prev);
					const existing = newMap.get(folderId);
					const item = existing?.item || findItem(folderId);

					if (item) {
						newMap.set(folderId, {
							item,
							children: items,
							isExpanded: true,
							isLoading: false,
						});
					}
					return newMap;
				});
			} catch (error) {
				console.error("Error loading folder contents:", error);
				setItemStates((prev) => {
					const newMap = new Map(prev);
					const existing = newMap.get(folderId);
					if (existing) {
						newMap.set(folderId, { ...existing, isLoading: false });
					}
					return newMap;
				});
			}
		},
		[fetchItems, findItem]
	);

	const toggleFolder = async (item: DriveItem) => {
		if (!item.isFolder) return;

		const state = itemStates.get(item.id);

		if (!state || state.children === null) {
			await loadFolderContents(item.id);
		} else {
			setItemStates((prev) => {
				const newMap = new Map(prev);
				newMap.set(item.id, {
					...state,
					isExpanded: !state.isExpanded,
				});
				return newMap;
			});
		}
	};

	const renderItem = (item: DriveItem, level: number = 0) => {
		const state = itemStates.get(item.id);
		const isExpanded = state?.isExpanded || false;
		const isLoading = state?.isLoading || false;
		const children = state?.children;
		const isFolder = item.isFolder;
		const isSelected = isFolder ? isFolderSelected(item.id) : isFileSelected(item.id);

		const childFolders = children?.filter((c) => c.isFolder) || [];
		const childFiles = children?.filter((c) => !c.isFolder) || [];

		const indentSize = 0.75;

		return (
			<div
				key={item.id}
				className="w-full sm:ml-[calc(var(--level)*1.25rem)]"
				style={
					{ marginLeft: `${level * indentSize}rem`, "--level": level } as React.CSSProperties & {
						"--level"?: number;
					}
				}
			>
				<div
					className={cn(
						"flex items-center group gap-1 sm:gap-2 h-auto py-1 sm:py-2 px-1 sm:px-2 rounded-md",
						isFolder && "hover:bg-accent cursor-pointer",
						!isFolder && "cursor-default opacity-60",
						isSelected && "bg-accent/50"
					)}
				>
					{isFolder ? (
						<button
							type="button"
							className="flex items-center justify-center w-3 h-3 sm:w-4 sm:h-4 shrink-0 bg-transparent border-0 p-0 cursor-pointer"
							onClick={(e) => {
								e.stopPropagation();
								toggleFolder(item);
							}}
							aria-label={isExpanded ? `Collapse ${item.name}` : `Expand ${item.name}`}
						>
							{isLoading ? (
								<Spinner size="xs" className="h-2.5 w-2.5 sm:h-3 sm:w-3" />
							) : isExpanded ? (
								<ChevronDown className="h-3 w-3 sm:h-4 sm:w-4" />
							) : (
								<ChevronRight className="h-3 w-3 sm:h-4 sm:w-4" />
							)}
						</button>
					) : (
						<span className="w-3 h-3 sm:w-4 sm:h-4 shrink-0" />
					)}

					<Checkbox
						checked={isSelected}
						onCheckedChange={() => {
							if (isFolder) {
								toggleFolderSelection(item.id, item.name);
							} else {
								toggleFileSelection(item.id, item.name);
							}
						}}
						className="shrink-0 h-3.5 w-3.5 sm:h-4 sm:w-4 border-slate-400/20 dark:border-white/20"
						onClick={(e) => e.stopPropagation()}
					/>

					<div className="shrink-0">
						{isFolder ? (
							isExpanded ? (
								<FolderOpen className="h-3 w-3 sm:h-4 sm:w-4 text-muted-foreground" />
							) : (
								<FolderClosed className="h-3 w-3 sm:h-4 sm:w-4 text-muted-foreground" />
							)
						) : (
							getFileIcon(item.mimeType, "h-3 w-3 sm:h-4 sm:w-4")
						)}
					</div>

					{isFolder ? (
						<button
							type="button"
							className="truncate flex-1 text-left text-xs sm:text-sm min-w-0 bg-transparent border-0 p-0 cursor-pointer"
							onClick={() => toggleFolder(item)}
						>
							{item.name}
						</button>
					) : (
						<span className="truncate flex-1 text-left text-xs sm:text-sm min-w-0">
							{item.name}
						</span>
					)}
				</div>

				{isExpanded && isFolder && children && (
					<div className="w-full">
						{childFolders.map((child) => renderItem(child, level + 1))}
						{childFiles.map((child) => renderItem(child, level + 1))}

						{children.length === 0 && (
							<div className="text-[10px] sm:text-xs text-muted-foreground py-1 sm:py-2 pl-1 sm:pl-2">
								Empty folder
							</div>
						)}
					</div>
				)}
			</div>
		);
	};

	return (
		<div className="border border-slate-400/20 dark:border-white/20 rounded-md w-full overflow-hidden">
			<ScrollArea className="h-[300px] sm:h-[450px] w-full">
				<div className="p-1 sm:p-2 pr-2 sm:pr-4 w-full overflow-x-hidden">
					<div className="mb-1 sm:mb-2 pb-1 sm:pb-2 border-b border-slate-400/20 dark:border-white/20">
						<div className="flex items-center gap-1 sm:gap-2 h-auto py-1 sm:py-2 px-1 sm:px-2 rounded-md hover:bg-accent cursor-pointer">
							<Checkbox
								checked={isFolderSelected("root")}
								onCheckedChange={() => toggleFolderSelection("root", rootLabel)}
								className="shrink-0 h-3.5 w-3.5 sm:h-4 sm:w-4 border-slate-400/20 dark:border-white/20"
							/>
							<HardDrive className="h-3 w-3 sm:h-4 sm:w-4 text-muted-foreground shrink-0" />
							<button
								type="button"
								className="font-semibold truncate text-xs sm:text-sm cursor-pointer bg-transparent border-0 p-0 text-left"
								onClick={() => toggleFolderSelection("root", rootLabel)}
							>
								{rootLabel}
							</button>
						</div>
					</div>

					{isLoadingRoot && (
						<div className="flex items-center justify-center py-4 sm:py-8">
							<Spinner size="sm" className="sm:h-6 sm:w-6 text-muted-foreground" />
						</div>
					)}

					<div className="w-full overflow-x-hidden">
						{!isLoadingRoot && rootItems.map((item) => renderItem(item, 0))}
					</div>

					{!isLoadingRoot && rootError && (
						<div className="text-center text-xs sm:text-sm text-amber-600 dark:text-amber-500 py-4 sm:py-8">
							{rootError.message.includes("authentication expired")
								? `${providerName} authentication has expired. Please re-authenticate above.`
								: `Failed to load ${providerName} contents.`}
						</div>
					)}

					{!isLoadingRoot && !rootError && rootItems.length === 0 && (
						<div className="text-center text-xs sm:text-sm text-muted-foreground py-4 sm:py-8">
							No files or folders found in your {providerName}
						</div>
					)}
				</div>
			</ScrollArea>
		</div>
	);
}
