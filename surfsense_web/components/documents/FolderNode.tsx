"use client";

import {
	AlertCircle,
	ChevronDown,
	ChevronRight,
	Eye,
	EyeOff,
	Folder,
	FolderOpen,
	FolderPlus,
	MoreHorizontal,
	Move,
	PenLine,
	RefreshCw,
	Trash2,
} from "lucide-react";
import React, { useCallback, useEffect, useRef, useState } from "react";
import { useDrag, useDrop } from "react-dnd";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
	ContextMenu,
	ContextMenuContent,
	ContextMenuItem,
	ContextMenuTrigger,
} from "@/components/ui/context-menu";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Spinner } from "@/components/ui/spinner";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import type { FolderSelectionState } from "./FolderTreeView";

export const DND_TYPES = {
	FOLDER: "FOLDER",
	DOCUMENT: "DOCUMENT",
} as const;

type DropZone = "top" | "middle" | "bottom";

export interface FolderDisplay {
	id: number;
	name: string;
	position: string;
	parentId: number | null;
	searchSpaceId: number;
}

interface FolderNodeProps {
	folder: FolderDisplay;
	depth: number;
	isExpanded: boolean;
	isRenaming: boolean;
	childCount: number;
	selectionState: FolderSelectionState;
	processingState: "idle" | "processing" | "failed";
	onToggleSelect: (folderId: number, selectAll: boolean) => void;
	onToggleExpand: (folderId: number) => void;
	onRename: (folder: FolderDisplay, newName: string) => void;
	onStartRename: (folderId: number) => void;
	onCancelRename: () => void;
	onDelete: (folder: FolderDisplay) => void;
	onMove: (folder: FolderDisplay) => void;
	onCreateSubfolder: (parentId: number) => void;
	onDropIntoFolder?: (
		itemType: "folder" | "document",
		itemId: number,
		targetFolderId: number
	) => void;
	onReorderFolder?: (folderId: number, beforePos: string | null, afterPos: string | null) => void;
	siblingPositions?: { before: string | null; after: string | null };
	disabledDropIds?: Set<number>;
	contextMenuOpen?: boolean;
	onContextMenuOpenChange?: (open: boolean) => void;
	isWatched?: boolean;
	onRescan?: (folder: FolderDisplay) => void;
	onStopWatching?: (folder: FolderDisplay) => void;
}

function getDropZone(
	monitor: { getClientOffset: () => { y: number } | null },
	element: HTMLElement
): DropZone {
	const offset = monitor.getClientOffset();
	if (!offset) return "middle";
	const rect = element.getBoundingClientRect();
	const y = offset.y - rect.top;
	const pct = y / rect.height;
	if (pct < 0.25) return "top";
	if (pct > 0.75) return "bottom";
	return "middle";
}

export const FolderNode = React.memo(function FolderNode({
	folder,
	depth,
	isExpanded,
	isRenaming,
	childCount,
	selectionState,
	processingState,
	onToggleSelect,
	onToggleExpand,
	onRename,
	onStartRename,
	onCancelRename,
	onDelete,
	onMove,
	onCreateSubfolder,
	onDropIntoFolder,
	onReorderFolder,
	siblingPositions,
	disabledDropIds,
	contextMenuOpen,
	onContextMenuOpenChange,
	isWatched,
	onRescan,
	onStopWatching,
}: FolderNodeProps) {
	const [renameValue, setRenameValue] = useState(folder.name);
	const inputRef = useRef<HTMLInputElement>(null);
	const rowRef = useRef<HTMLDivElement>(null);
	const [dropZone, setDropZone] = useState<DropZone | null>(null);

	const [{ isDragging }, drag] = useDrag(
		() => ({
			type: DND_TYPES.FOLDER,
			item: { id: folder.id, position: folder.position, parentId: folder.parentId },
			collect: (monitor) => ({ isDragging: monitor.isDragging() }),
		}),
		[folder.id, folder.position, folder.parentId]
	);

	const [{ isOver, canDrop }, drop] = useDrop(
		() => ({
			accept: [DND_TYPES.FOLDER, DND_TYPES.DOCUMENT],
			canDrop: (item: { id: number }) => {
				if (item.id === folder.id) return false;
				if (disabledDropIds?.has(item.id)) return false;
				return true;
			},
			hover: (_item, monitor) => {
				if (!rowRef.current || !monitor.isOver({ shallow: true })) {
					setDropZone(null);
					return;
				}
				setDropZone(getDropZone(monitor, rowRef.current));
			},
			drop: (item: { id: number }, monitor) => {
				if (!rowRef.current) return;
				const zone = getDropZone(monitor, rowRef.current);
				const type = monitor.getItemType();

				if (zone === "middle") {
					if (type === DND_TYPES.FOLDER) {
						onDropIntoFolder?.("folder", item.id, folder.id);
					} else {
						onDropIntoFolder?.("document", item.id, folder.id);
					}
				} else if (type === DND_TYPES.FOLDER && onReorderFolder && siblingPositions) {
					if (zone === "top") {
						onReorderFolder(item.id, siblingPositions.before, folder.position);
					} else {
						onReorderFolder(item.id, folder.position, siblingPositions.after);
					}
				}
				setDropZone(null);
			},
			collect: (monitor) => ({
				isOver: monitor.isOver({ shallow: true }),
				canDrop: monitor.canDrop(),
			}),
		}),
		[
			folder.id,
			folder.position,
			disabledDropIds,
			onDropIntoFolder,
			onReorderFolder,
			siblingPositions,
		]
	);

	useEffect(() => {
		if (!isOver) setDropZone(null);
	}, [isOver]);

	const attachRef = useCallback(
		(node: HTMLDivElement | null) => {
			rowRef.current = node;
			drag(drop(node));
		},
		[drag, drop]
	);

	useEffect(() => {
		if (isRenaming && inputRef.current) {
			inputRef.current.focus();
			inputRef.current.select();
		}
	}, [isRenaming]);

	const handleRenameSubmit = useCallback(() => {
		const trimmed = renameValue.trim();
		if (trimmed && trimmed !== folder.name) {
			onRename(folder, trimmed);
		}
		onCancelRename();
	}, [renameValue, folder, onRename, onCancelRename]);

	const handleRenameKeyDown = useCallback(
		(e: React.KeyboardEvent) => {
			if (e.key === "Enter") {
				e.preventDefault();
				handleRenameSubmit();
			} else if (e.key === "Escape") {
				e.preventDefault();
				setRenameValue(folder.name);
				onCancelRename();
			}
		},
		[handleRenameSubmit, folder.name, onCancelRename]
	);

	const startRename = useCallback(() => {
		setRenameValue(folder.name);
		onStartRename(folder.id);
	}, [folder, onStartRename]);

	const handleCheckChange = useCallback(() => {
		onToggleSelect(folder.id, selectionState !== "all");
	}, [folder.id, selectionState, onToggleSelect]);

	const FolderIcon = isExpanded ? FolderOpen : Folder;

	return (
		<ContextMenu onOpenChange={onContextMenuOpenChange}>
			<ContextMenuTrigger asChild disabled={isRenaming}>
				{/* biome-ignore lint/a11y/useSemanticElements: div required for drag/drop refs */}
				<div
					ref={attachRef}
					role="button"
					tabIndex={0}
					className={cn(
						"group relative flex h-8 items-center gap-1 rounded-md px-1 text-sm hover:bg-accent/50 cursor-pointer select-none",
						isExpanded && "font-medium",
						isDragging && "opacity-40",
						isOver && canDrop && dropZone === "middle" && "bg-accent ring-1 ring-primary/40",
						isOver && canDrop && dropZone === "top" && "border-t-2 border-primary",
						isOver && canDrop && dropZone === "bottom" && "border-b-2 border-primary",
						isOver && !canDrop && "cursor-not-allowed"
					)}
					style={{ paddingLeft: `${depth * 16 + 4}px` }}
				onClick={() => {
					onToggleExpand(folder.id);
				}}
				onKeyDown={(e) => {
					if (e.key === "Enter" || e.key === " ") {
						e.preventDefault();
						onToggleExpand(folder.id);
					}
				}}
					onDoubleClick={(e) => {
						e.stopPropagation();
						startRename();
					}}
				>
					<span className="flex h-4 w-4 shrink-0 items-center justify-center">
						{isExpanded ? (
							<ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
						) : (
							<ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
						)}
					</span>

					{processingState !== "idle" && selectionState === "none" ? (
						<>
							<Tooltip>
								<TooltipTrigger asChild>
									<span className="flex h-3.5 w-3.5 shrink-0 items-center justify-center group-hover:hidden">
										{processingState === "processing" ? (
											<Spinner size="xs" className="text-primary" />
										) : (
											<AlertCircle className="h-3.5 w-3.5 text-destructive" />
										)}
									</span>
								</TooltipTrigger>
								<TooltipContent side="top">
									{processingState === "processing"
										? "Syncing folder contents"
										: "Some files failed to process"}
								</TooltipContent>
							</Tooltip>
							<Checkbox
								checked={false}
								onCheckedChange={handleCheckChange}
								onClick={(e) => e.stopPropagation()}
								className="h-3.5 w-3.5 shrink-0 hidden group-hover:flex"
							/>
						</>
					) : (
						<Checkbox
							checked={
								selectionState === "all" ? true : selectionState === "some" ? "indeterminate" : false
							}
							onCheckedChange={handleCheckChange}
							onClick={(e) => e.stopPropagation()}
							className="h-3.5 w-3.5 shrink-0"
						/>
					)}

					<FolderIcon className="h-4 w-4 shrink-0 text-muted-foreground" />

					{isRenaming ? (
						<input
							ref={inputRef}
							type="text"
							value={renameValue}
							onChange={(e) => setRenameValue(e.target.value)}
							onBlur={handleRenameSubmit}
							onKeyDown={handleRenameKeyDown}
							onClick={(e) => e.stopPropagation()}
							placeholder="Enter folder name"
							className="flex-1 min-w-0 bg-transparent px-1 py-0.5 text-sm outline-none caret-primary placeholder:text-muted-foreground/50"
						/>
					) : (
						<span className="flex-1 min-w-0 truncate">{folder.name}</span>
					)}

					{!isRenaming && childCount > 0 && (
						<span className="shrink-0 text-[10px] text-muted-foreground tabular-nums">
							{childCount}
						</span>
					)}

					{!isRenaming && (
						<DropdownMenu>
							<DropdownMenuTrigger asChild>
								<Button
									variant="ghost"
									size="icon"
									className="hidden sm:inline-flex h-6 w-6 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity"
									onClick={(e) => e.stopPropagation()}
								>
									<MoreHorizontal className="h-3.5 w-3.5" />
								</Button>
							</DropdownMenuTrigger>
						<DropdownMenuContent align="end" className="w-40">
							{isWatched && onRescan && (
								<DropdownMenuItem
									onClick={(e) => {
										e.stopPropagation();
										onRescan(folder);
									}}
								>
									<RefreshCw className="mr-2 h-4 w-4" />
									Re-scan
								</DropdownMenuItem>
							)}
							{isWatched && onStopWatching && (
								<DropdownMenuItem
									onClick={(e) => {
										e.stopPropagation();
										onStopWatching(folder);
									}}
								>
									<EyeOff className="mr-2 h-4 w-4" />
									Stop watching
								</DropdownMenuItem>
							)}
							<DropdownMenuItem
								onClick={(e) => {
									e.stopPropagation();
									onCreateSubfolder(folder.id);
								}}
							>
								<FolderPlus className="mr-2 h-4 w-4" />
								New subfolder
							</DropdownMenuItem>
							<DropdownMenuItem
								onClick={(e) => {
									e.stopPropagation();
									startRename();
								}}
							>
								<PenLine className="mr-2 h-4 w-4" />
								Rename
							</DropdownMenuItem>
							<DropdownMenuItem
								onClick={(e) => {
									e.stopPropagation();
									onMove(folder);
								}}
							>
								<Move className="mr-2 h-4 w-4" />
								Move to...
							</DropdownMenuItem>
							<DropdownMenuItem
								className="text-destructive focus:text-destructive"
								onClick={(e) => {
									e.stopPropagation();
									onDelete(folder);
								}}
							>
								<Trash2 className="mr-2 h-4 w-4" />
								Delete
							</DropdownMenuItem>
						</DropdownMenuContent>
						</DropdownMenu>
					)}
				</div>
			</ContextMenuTrigger>

		{!isRenaming && contextMenuOpen && (
			<ContextMenuContent className="w-40">
				{isWatched && onRescan && (
					<ContextMenuItem onClick={() => onRescan(folder)}>
						<RefreshCw className="mr-2 h-4 w-4" />
						Re-scan
					</ContextMenuItem>
				)}
				{isWatched && onStopWatching && (
					<ContextMenuItem onClick={() => onStopWatching(folder)}>
						<EyeOff className="mr-2 h-4 w-4" />
						Stop watching
					</ContextMenuItem>
				)}
				<ContextMenuItem onClick={() => onCreateSubfolder(folder.id)}>
					<FolderPlus className="mr-2 h-4 w-4" />
					New subfolder
				</ContextMenuItem>
				<ContextMenuItem onClick={() => startRename()}>
					<PenLine className="mr-2 h-4 w-4" />
					Rename
				</ContextMenuItem>
				<ContextMenuItem onClick={() => onMove(folder)}>
					<Move className="mr-2 h-4 w-4" />
					Move to...
				</ContextMenuItem>
				<ContextMenuItem
					className="text-destructive focus:text-destructive"
					onClick={() => onDelete(folder)}
				>
					<Trash2 className="mr-2 h-4 w-4" />
					Delete
				</ContextMenuItem>
			</ContextMenuContent>
		)}
		</ContextMenu>
	);
});
