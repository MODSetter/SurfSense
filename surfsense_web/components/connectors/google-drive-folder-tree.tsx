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
import { authenticatedFetch } from "@/lib/auth-utils";

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
}: GoogleDriveFolderTreeProps) {
	const [rootItems, setRootItems] = useState<DriveItem[]>([]);
	const [itemStates, setItemStates] = useState<Map<string, ItemTreeNode>>(new Map());
	const [isLoadingRoot, setIsLoadingRoot] = useState(false);
	const [isInitialized, setIsInitialized] = useState(false);

	// Helper to check if a folder is selected
	const isFolderSelected = (folderId: string): boolean => {
		return selectedFolders.some((f) => f.id === folderId);
	};

	// Handle folder checkbox toggle
	const toggleFolderSelection = (folderId: string, folderName: string) => {
		if (isFolderSelected(folderId)) {
			// Remove from selection
			onSelectFolders(selectedFolders.filter((f) => f.id !== folderId));
		} else {
			// Add to selection
			onSelectFolders([...selectedFolders, { id: folderId, name: folderName }]);
		}
	};

	// Load root items (folders and files) on mount
	const loadRootItems = async () => {
		if (isInitialized) return; // Already loaded

		setIsLoadingRoot(true);
		try {
			const response = await authenticatedFetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/connectors/${connectorId}/google-drive/folders`
			);
			if (!response.ok) throw new Error("Failed to load items");

			const data = await response.json();
			setRootItems(data.items || []);
			setIsInitialized(true);
		} catch (error) {
			console.error("Error loading root items:", error);
		} finally {
			setIsLoadingRoot(false);
		}
	};

	// Helper function to find an item recursively through all loaded items
	const findItem = (itemId: string): DriveItem | undefined => {
		// First check if we have it in itemStates
		const state = itemStates.get(itemId);
		if (state?.item) return state.item;

		// Check root items
		const rootItem = rootItems.find((item) => item.id === itemId);
		if (rootItem) return rootItem;

		// Recursively search through all loaded children
		for (const [, nodeState] of itemStates) {
			if (nodeState.children) {
				const found = nodeState.children.find((child) => child.id === itemId);
				if (found) return found;
			}
		}

		return undefined;
	};

	// Load children (folders and files) for a specific folder
	const loadFolderContents = async (folderId: string) => {
		try {
			// Set loading state
			setItemStates((prev) => {
				const newMap = new Map(prev);
				const existing = newMap.get(folderId);
				if (existing) {
					newMap.set(folderId, { ...existing, isLoading: true });
				} else {
					// First time loading this folder - create initial state
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

			const response = await authenticatedFetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/connectors/${connectorId}/google-drive/folders?parent_id=${folderId}`
			);
			if (!response.ok) throw new Error("Failed to load folder contents");

			const data = await response.json();
			const items = data.items || [];

			// Check if folder only contains files (no subfolders)
			const hasSubfolders = items.some((item: DriveItem) => item.isFolder);

			// Update item state with loaded children
			setItemStates((prev) => {
				const newMap = new Map(prev);
				const existing = newMap.get(folderId);
				const item = existing?.item || findItem(folderId);

				if (item) {
					newMap.set(folderId, {
						item,
						children: items,
						isExpanded: true, // Always expand after loading
						isLoading: false,
					});
				} else {
					console.error(`Could not find item for folderId: ${folderId}`);
				}
				return newMap;
			});
		} catch (error) {
			console.error("Error loading folder contents:", error);
			// Clear loading state on error
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

	// Toggle folder expansion
	const toggleFolder = async (item: DriveItem) => {
		if (!item.isFolder) return; // Only folders can be expanded

		const state = itemStates.get(item.id);

		if (!state || state.children === null) {
			// First time expanding - load children
			await loadFolderContents(item.id);
		} else {
			// Toggle expansion state
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

	// Recursive render function for item tree
	const renderItem = (item: DriveItem, level: number = 0) => {
		const state = itemStates.get(item.id);
		const isExpanded = state?.isExpanded || false;
		const isLoading = state?.isLoading || false;
		const children = state?.children;
		const isSelected = isFolderSelected(item.id);
		const isFolder = item.isFolder;

		// Separate folders and files for children
		const childFolders = children?.filter((c) => c.isFolder) || [];
		const childFiles = children?.filter((c) => !c.isFolder) || [];

		return (
			<div key={item.id} className="w-full" style={{ marginLeft: `${level * 1.25}rem` }}>
				<div
					className={cn(
						"flex items-center gap-2 h-auto py-2 px-2 rounded-md",
						isFolder && "hover:bg-accent cursor-pointer",
						!isFolder && "cursor-default opacity-60",
						isSelected && isFolder && "bg-accent/50"
					)}
				>
					{/* Expand/Collapse Icon (only for folders) */}
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
						<span className="w-4 h-4 shrink-0" /> // Empty space for alignment
					)}

					{/* Checkbox (only for folders) */}
					{isFolder && (
						<Checkbox
							checked={isSelected}
							onCheckedChange={() => toggleFolderSelection(item.id, item.name)}
							className="shrink-0"
							onClick={(e) => e.stopPropagation()}
						/>
					)}

					{/* Icon */}
					<div className="shrink-0" style={{ marginLeft: isFolder ? "0" : "1.25rem" }}>
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

					{/* Item Name */}
					<span
						className="truncate flex-1 text-left text-sm min-w-0"
						onClick={() => isFolder && toggleFolder(item)}
					>
						{item.name}
					</span>
				</div>

				{/* Render children if expanded (folders first, then files) */}
				{isExpanded && isFolder && children && (
					<div className="w-full">
						{/* Render folders first */}
						{childFolders.map((child) => renderItem(child, level + 1))}

						{/* Render files */}
						{childFiles.map((child) => renderItem(child, level + 1))}

						{/* Empty state */}
						{children.length === 0 && (
							<div className="text-xs text-muted-foreground py-2 pl-2">Empty folder</div>
						)}
					</div>
				)}
			</div>
		);
	};

	// Initialize on first render
	if (!isInitialized && !isLoadingRoot) {
		loadRootItems();
	}

	return (
		<div className="border rounded-md w-full overflow-hidden">
			<ScrollArea className="h-[450px] w-full">
				<div className="p-2 pr-4 w-full overflow-x-hidden">
					{/* My Drive Header (always visible, selectable) */}
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

					{/* Loading indicator */}
					{isLoadingRoot && (
						<div className="flex items-center justify-center py-8">
							<Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
						</div>
					)}

					{/* Root items (folders and files) - same level as Google Drive shows */}
					<div className="w-full overflow-x-hidden">
						{!isLoadingRoot && rootItems.map((item) => renderItem(item, 0))}
					</div>

					{/* Empty state */}
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
