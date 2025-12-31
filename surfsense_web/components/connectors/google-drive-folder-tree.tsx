"use client";

import {
	ChevronDown,
	ChevronRight,
	File,
	FileText,
	Folder,
	FolderOpen,
	HardDrive,
	Image,
	Loader2,
	Sheet,
	Presentation,
} from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import { useGoogleDriveFolders } from "@/hooks/use-google-drive-folders";
import { connectorsApiService } from "@/lib/apis/connectors-api.service";

interface DriveItem {
	id: string;
	name: string;
	mimeType: string;
	isFolder: boolean;
	parents?: string[];
	size?: number;
	iconLink?: string;
}

interface ItemTreeNode {
	item: DriveItem;
	children: DriveItem[] | null; // null = not loaded, [] = loaded but empty
	isExpanded: boolean;
	isLoading: boolean;
}

interface SelectedFolder {
	id: string;
	name: string;
}

interface GoogleDriveFolderTreeProps {
	connectorId: number;
	selectedFolders: SelectedFolder[];
	onSelectFolders: (folders: SelectedFolder[]) => void;
	selectedFiles?: SelectedFolder[];
	onSelectFiles?: (files: SelectedFolder[]) => void;
}

// Helper to get appropriate icon for file type
function getFileIcon(mimeType: string, className: string = "h-4 w-4") {
	if (mimeType.includes("spreadsheet") || mimeType.includes("excel")) {
		return <Sheet className={`${className} text-green-600`} />;
	}
	if (mimeType.includes("presentation") || mimeType.includes("powerpoint")) {
		return <Presentation className={`${className} text-orange-600`} />;
	}
	if (mimeType.includes("document") || mimeType.includes("word") || mimeType.includes("text")) {
		return <FileText className={`${className} text-blue-600`} />;
	}
	if (mimeType.includes("image")) {
		return <Image className={`${className} text-purple-600`} />;
	}
	return <File className={`${className} text-gray-500`} />;
}

export function GoogleDriveFolderTree({
	connectorId,
	selectedFolders,
	onSelectFolders,
	selectedFiles = [],
	onSelectFiles = () => {},
}: GoogleDriveFolderTreeProps) {
	const [itemStates, setItemStates] = useState<Map<string, ItemTreeNode>>(new Map());

	const { data: rootData, isLoading: isLoadingRoot } = useGoogleDriveFolders({
		connectorId,
	});

	const rootItems = rootData?.items || [];

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

	/**
	 * Find an item by ID across all loaded items (root and nested).
	 */
	const findItem = (itemId: string): DriveItem | undefined => {
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
	};

	/**
	 * Load and display contents of a specific folder.
	 */
	const loadFolderContents = async (folderId: string) => {
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

			const data = await connectorsApiService.listGoogleDriveFolders({
				connector_id: connectorId,
				parent_id: folderId,
			});
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
				} else {
					console.error(`Could not find item for folderId: ${folderId}`);
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
	};

	/**
	 * Toggle folder expand/collapse state.
	 */
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

	/**
	 * Render a single item (folder or file) with its children.
	 */
	const renderItem = (item: DriveItem, level: number = 0) => {
		const state = itemStates.get(item.id);
		const isExpanded = state?.isExpanded || false;
		const isLoading = state?.isLoading || false;
		const children = state?.children;
		const isFolder = item.isFolder;
		const isSelected = isFolder ? isFolderSelected(item.id) : isFileSelected(item.id);

		const childFolders = children?.filter((c) => c.isFolder) || [];
		const childFiles = children?.filter((c) => !c.isFolder) || [];

		return (
			<div key={item.id} className="w-full" style={{ marginLeft: `${level * 1.25}rem` }}>
				<div
					className={cn(
						"flex items-center group gap-2 h-auto py-2 px-2 rounded-md hover:bg-accent cursor-pointer",
						isSelected && "bg-accent/50"
					)}
				>
					{isFolder ? (
						<span
							className="flex items-center justify-center w-4 h-4 shrink-0"
							onClick={(e) => {
								e.stopPropagation();
								toggleFolder(item);
							}}
						>
							{isLoading ? (
								<Loader2 className="h-3 w-3 animate-spin" />
							) : isExpanded ? (
								<ChevronDown className="h-4 w-4" />
							) : (
								<ChevronRight className="h-4 w-4" />
							)}
						</span>
					) : (
						<span className="w-4 h-4 shrink-0" />
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
						className="shrink-0 z-20 group-hover:border-white group-hover:border"
						onClick={(e) => e.stopPropagation()}
					/>

					<div className="shrink-0">
						{isFolder ? (
							isExpanded ? (
								<FolderOpen className="h-4 w-4 text-blue-500" />
							) : (
								<Folder className="h-4 w-4 text-gray-500" />
							)
						) : (
							getFileIcon(item.mimeType, "h-4 w-4")
						)}
					</div>

					<span
						className="truncate flex-1 text-left text-sm min-w-0"
						onClick={() => isFolder && toggleFolder(item)}
					>
						{item.name}
					</span>
				</div>

				{isExpanded && isFolder && children && (
					<div className="w-full">
						{childFolders.map((child) => renderItem(child, level + 1))}
						{childFiles.map((child) => renderItem(child, level + 1))}

						{children.length === 0 && (
							<div className="text-xs text-muted-foreground py-2 pl-2">Empty folder</div>
						)}
					</div>
				)}
			</div>
		);
	};

	return (
		<div className="border rounded-md w-full overflow-hidden">
			<ScrollArea className="h-[450px] w-full">
				<div className="p-2 pr-4 w-full overflow-x-hidden">
					<div className="mb-2 pb-2 border-b">
						<div className="flex items-center gap-2 h-auto py-2 px-2 rounded-md hover:bg-accent cursor-pointer">
							<Checkbox
								checked={isFolderSelected("root")}
								onCheckedChange={() => toggleFolderSelection("root", "My Drive")}
								className="shrink-0"
							/>
							<HardDrive className="h-4 w-4 text-primary shrink-0" />
							<span className="font-semibold truncate" onClick={() => toggleFolderSelection("root", "My Drive")}>
								My Drive
							</span>
						</div>
					</div>

					{isLoadingRoot && (
						<div className="flex items-center justify-center py-8">
							<Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
						</div>
					)}

					<div className="w-full overflow-x-hidden">
						{!isLoadingRoot && rootItems.map((item) => renderItem(item, 0))}
					</div>

					{!isLoadingRoot && rootItems.length === 0 && (
						<div className="text-center text-sm text-muted-foreground py-8">
							No files or folders found in your Google Drive
						</div>
					)}
				</div>
			</ScrollArea>
		</div>
	);
}
