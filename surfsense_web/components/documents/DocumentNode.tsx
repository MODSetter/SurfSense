"use client";

import {
	AlertCircle,
	Clock,
	Download,
	Eye,
	History,
	MoreHorizontal,
	Move,
	Pencil,
	RotateCcw,
	Trash2,
} from "lucide-react";
import React, { useCallback, useRef, useState } from "react";
import { useDrag } from "react-dnd";
import { getDocumentTypeIcon } from "@/components/documents/DocumentTypeIcon";
import { ExportContextItems, ExportDropdownItems } from "@/components/shared/ExportMenuItems";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
	ContextMenu,
	ContextMenuContent,
	ContextMenuItem,
	ContextMenuSub,
	ContextMenuSubContent,
	ContextMenuSubTrigger,
	ContextMenuTrigger,
} from "@/components/ui/context-menu";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuSub,
	DropdownMenuSubContent,
	DropdownMenuSubTrigger,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Spinner } from "@/components/ui/spinner";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { DocumentTypeEnum } from "@/contracts/types/document.types";
import { cn } from "@/lib/utils";
import { DND_TYPES } from "./FolderNode";
import { isVersionableType } from "./version-history";

const EDITABLE_DOCUMENT_TYPES = new Set(["FILE", "NOTE"]);

export interface DocumentNodeDoc {
	id: number;
	title: string;
	document_type: string;
	folderId: number | null;
	status?: { state: string; reason?: string | null };
}

interface DocumentNodeProps {
	doc: DocumentNodeDoc;
	depth: number;
	isMentioned: boolean;
	onToggleChatMention: (doc: DocumentNodeDoc, isMentioned: boolean) => void;
	onPreview: (doc: DocumentNodeDoc) => void;
	onEdit: (doc: DocumentNodeDoc) => void;
	onDelete: (doc: DocumentNodeDoc) => void;
	onMove: (doc: DocumentNodeDoc) => void;
	onReset?: (doc: DocumentNodeDoc) => void;
	onExport?: (doc: DocumentNodeDoc, format: string) => void;
	onVersionHistory?: (doc: DocumentNodeDoc) => void;
	canDelete?: boolean;
	canMove?: boolean;
	canMention?: boolean;
	canEdit?: boolean;
	contextMenuOpen?: boolean;
	onContextMenuOpenChange?: (open: boolean) => void;
}

export const DocumentNode = React.memo(function DocumentNode({
	doc,
	depth,
	isMentioned,
	onToggleChatMention,
	onPreview,
	onEdit,
	onDelete,
	onMove,
	onReset,
	onExport,
	onVersionHistory,
	canDelete = true,
	canMove = true,
	canMention = true,
	canEdit = true,
	contextMenuOpen,
	onContextMenuOpenChange,
}: DocumentNodeProps) {
	const statusState = doc.status?.state ?? "ready";
	const isFailed = statusState === "failed";
	const isProcessing = statusState === "pending" || statusState === "processing";
	const isUnavailable = isProcessing || isFailed;
	const isMemoryDocument =
		doc.document_type === "USER_MEMORY" || doc.document_type === "TEAM_MEMORY";
	const isSelectable = canMention && !isUnavailable;
	const isEditable =
		canEdit &&
		(isMemoryDocument || EDITABLE_DOCUMENT_TYPES.has(doc.document_type)) &&
		!isUnavailable;

	const handleCheckChange = useCallback(() => {
		if (isSelectable) {
			onToggleChatMention(doc, isMentioned);
		}
	}, [doc, isMentioned, isSelectable, onToggleChatMention]);

	const handlePrimaryClick = useCallback(() => {
		if (canMention) {
			handleCheckChange();
			return;
		}
		onPreview(doc);
	}, [canMention, doc, handleCheckChange, onPreview]);

	const [{ isDragging }, drag] = useDrag(
		() => ({
			type: DND_TYPES.DOCUMENT,
			item: { id: doc.id },
			canDrag: canMove,
			collect: (monitor) => ({ isDragging: monitor.isDragging() }),
		}),
		[canMove, doc.id]
	);

	const [dropdownOpen, setDropdownOpen] = useState(false);
	const [exporting, setExporting] = useState<string | null>(null);
	const [titleTooltipOpen, setTitleTooltipOpen] = useState(false);
	const rowRef = useRef<HTMLDivElement>(null);
	const titleRef = useRef<HTMLSpanElement>(null);

	const handleExport = useCallback(
		(format: string) => {
			if (!onExport) return;
			setExporting(format);
			onExport(doc, format);
			setTimeout(() => setExporting(null), 2000);
		},
		[doc, onExport]
	);

	const handleTitleTooltipOpenChange = useCallback((open: boolean) => {
		if (open && titleRef.current) {
			setTitleTooltipOpen(titleRef.current.scrollWidth > titleRef.current.clientWidth);
		} else {
			setTitleTooltipOpen(false);
		}
	}, []);

	const attachRef = useCallback(
		(node: HTMLDivElement | null) => {
			(rowRef as React.MutableRefObject<HTMLDivElement | null>).current = node;
			if (canMove) {
				drag(node);
			}
		},
		[canMove, drag]
	);

	return (
		<ContextMenu onOpenChange={onContextMenuOpenChange}>
			<ContextMenuTrigger asChild>
				<div
					ref={attachRef}
					className={cn(
						"group flex h-8 w-full items-center gap-2.5 rounded-md px-1 text-sm hover:bg-accent hover:text-accent-foreground cursor-pointer select-none text-left",
						isMentioned && "bg-accent text-accent-foreground",
						isDragging && "opacity-40"
					)}
					style={{ paddingLeft: `${depth * 16 + 4}px` }}
				>
					{(() => {
						if (statusState === "pending") {
							return (
								<Tooltip>
									<TooltipTrigger asChild>
										<span className="flex h-3.5 w-3.5 shrink-0 items-center justify-center">
											<Clock className="h-3.5 w-3.5 text-muted-foreground/60" />
										</span>
									</TooltipTrigger>
									<TooltipContent side="top">Pending: waiting to be synced</TooltipContent>
								</Tooltip>
							);
						}
						if (statusState === "processing") {
							return (
								<Tooltip>
									<TooltipTrigger asChild>
										<span className="flex h-3.5 w-3.5 shrink-0 items-center justify-center">
											<Spinner size="xs" className="text-primary" />
										</span>
									</TooltipTrigger>
									<TooltipContent side="top">Syncing</TooltipContent>
								</Tooltip>
							);
						}
						if (statusState === "failed") {
							return (
								<Tooltip>
									<TooltipTrigger asChild>
										<span className="flex h-3.5 w-3.5 shrink-0 items-center justify-center">
											<AlertCircle className="h-3.5 w-3.5 text-destructive" />
										</span>
									</TooltipTrigger>
									<TooltipContent side="top">
										{doc.status?.reason || "Processing failed"}
									</TooltipContent>
								</Tooltip>
							);
						}
						return (
							<>
								{isMemoryDocument ? (
									<span aria-disabled="true" className="h-3.5 w-3.5 shrink-0 cursor-default">
										<Checkbox
											checked={false}
											disabled
											aria-disabled
											className="h-3.5 w-3.5 pointer-events-none"
										/>
									</span>
								) : canMention ? (
									<Checkbox
										checked={isMentioned}
										onCheckedChange={handleCheckChange}
										onClick={(e) => e.stopPropagation()}
										className="h-3.5 w-3.5 shrink-0"
									/>
								) : (
									<span className="flex h-3.5 w-3.5 shrink-0 items-center justify-center">
										{getDocumentTypeIcon(
											doc.document_type as DocumentTypeEnum,
											"h-3.5 w-3.5 text-muted-foreground"
										)}
									</span>
								)}
							</>
						);
					})()}

					<Tooltip
						delayDuration={600}
						open={titleTooltipOpen}
						onOpenChange={handleTitleTooltipOpenChange}
					>
						<TooltipTrigger asChild>
							<Button
								type="button"
								variant="ghost"
								aria-disabled={canMention ? !isSelectable : false}
								onClick={handlePrimaryClick}
								className="h-full min-w-0 flex-1 justify-start bg-transparent px-0 py-0 text-left font-normal text-inherit hover:bg-transparent hover:text-inherit"
							>
								<span ref={titleRef} className="min-w-0 flex-1 truncate">
									{doc.title}
								</span>
							</Button>
						</TooltipTrigger>
						<TooltipContent side="bottom" className="max-w-xs break-words">
							{doc.title}
						</TooltipContent>
					</Tooltip>

					<span className="relative shrink-0 flex items-center justify-center h-6 w-6">
						{getDocumentTypeIcon(
							doc.document_type as DocumentTypeEnum,
							"h-3.5 w-3.5 text-muted-foreground"
						) && (
							<span
								className={cn(
									"absolute inset-0 flex items-center justify-center transition-opacity pointer-events-none",
									dropdownOpen ? "opacity-0" : "group-hover:opacity-0"
								)}
							>
								{getDocumentTypeIcon(
									doc.document_type as DocumentTypeEnum,
									"h-3.5 w-3.5 text-muted-foreground"
								)}
							</span>
						)}

						<DropdownMenu open={dropdownOpen} onOpenChange={setDropdownOpen}>
							<DropdownMenuTrigger asChild>
								<Button
									variant="ghost"
									size="icon"
									className={cn(
										"hidden sm:inline-flex h-6 w-6 shrink-0 hover:bg-transparent",
										dropdownOpen
											? "opacity-100 bg-accent hover:bg-accent"
											: "opacity-0 group-hover:opacity-100"
									)}
									onClick={(e) => e.stopPropagation()}
								>
									<MoreHorizontal className="h-3.5 w-3.5 text-muted-foreground" />
								</Button>
							</DropdownMenuTrigger>
							<DropdownMenuContent
								align="end"
								className="w-40"
								onClick={(e) => e.stopPropagation()}
							>
								<DropdownMenuItem onClick={() => onPreview(doc)} disabled={isUnavailable}>
									<Eye className="mr-2 h-4 w-4" />
									Open
								</DropdownMenuItem>
								{isEditable && (
									<DropdownMenuItem onClick={() => onEdit(doc)}>
										<Pencil className="mr-2 h-4 w-4" />
										Edit
									</DropdownMenuItem>
								)}
								{canMove && (
									<DropdownMenuItem onClick={() => onMove(doc)}>
										<Move className="mr-2 h-4 w-4" />
										Move to...
									</DropdownMenuItem>
								)}
								{onExport && isMemoryDocument ? (
									<DropdownMenuItem disabled={isUnavailable} onClick={() => handleExport("md")}>
										<Download className="mr-2 h-4 w-4" />
										Export as MD
									</DropdownMenuItem>
								) : onExport ? (
									<DropdownMenuSub>
										<DropdownMenuSubTrigger disabled={isUnavailable}>
											<Download className="mr-2 h-4 w-4" />
											Export
										</DropdownMenuSubTrigger>
										<DropdownMenuSubContent className="min-w-[180px]">
											<ExportDropdownItems onExport={handleExport} exporting={exporting} />
										</DropdownMenuSubContent>
									</DropdownMenuSub>
								) : null}
								{onVersionHistory && isVersionableType(doc.document_type) && (
									<DropdownMenuItem disabled={isUnavailable} onClick={() => onVersionHistory(doc)}>
										<History className="mr-2 h-4 w-4" />
										Versions
									</DropdownMenuItem>
								)}
								{isMemoryDocument && onReset && (
									<DropdownMenuItem onClick={() => onReset(doc)}>
										<RotateCcw className="mr-2 h-4 w-4" />
										Reset
									</DropdownMenuItem>
								)}
								{canDelete && (
									<DropdownMenuItem disabled={isProcessing} onClick={() => onDelete(doc)}>
										<Trash2 className="mr-2 h-4 w-4" />
										Delete
									</DropdownMenuItem>
								)}
							</DropdownMenuContent>
						</DropdownMenu>
					</span>
				</div>
			</ContextMenuTrigger>

			{contextMenuOpen && (
				<ContextMenuContent className="w-40" onClick={(e) => e.stopPropagation()}>
					<ContextMenuItem onClick={() => onPreview(doc)} disabled={isUnavailable}>
						<Eye className="mr-2 h-4 w-4" />
						Open
					</ContextMenuItem>
					{isEditable && (
						<ContextMenuItem onClick={() => onEdit(doc)}>
							<Pencil className="mr-2 h-4 w-4" />
							Edit
						</ContextMenuItem>
					)}
					{canMove && (
						<ContextMenuItem onClick={() => onMove(doc)}>
							<Move className="mr-2 h-4 w-4" />
							Move to...
						</ContextMenuItem>
					)}
					{onExport && isMemoryDocument ? (
						<ContextMenuItem disabled={isUnavailable} onClick={() => handleExport("md")}>
							<Download className="mr-2 h-4 w-4" />
							Export as MD
						</ContextMenuItem>
					) : onExport ? (
						<ContextMenuSub>
							<ContextMenuSubTrigger disabled={isUnavailable}>
								<Download className="mr-2 h-4 w-4" />
								Export
							</ContextMenuSubTrigger>
							<ContextMenuSubContent className="min-w-[180px]">
								<ExportContextItems onExport={handleExport} exporting={exporting} />
							</ContextMenuSubContent>
						</ContextMenuSub>
					) : null}
					{onVersionHistory && isVersionableType(doc.document_type) && (
						<ContextMenuItem disabled={isUnavailable} onClick={() => onVersionHistory(doc)}>
							<History className="mr-2 h-4 w-4" />
							Versions
						</ContextMenuItem>
					)}
					{isMemoryDocument && onReset && (
						<ContextMenuItem onClick={() => onReset(doc)}>
							<RotateCcw className="mr-2 h-4 w-4" />
							Reset
						</ContextMenuItem>
					)}
					{canDelete && (
						<ContextMenuItem disabled={isProcessing} onClick={() => onDelete(doc)}>
							<Trash2 className="mr-2 h-4 w-4" />
							Delete
						</ContextMenuItem>
					)}
				</ContextMenuContent>
			)}
		</ContextMenu>
	);
});
