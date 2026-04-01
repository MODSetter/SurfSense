"use client";

import {
	AlertCircle,
	Clock,
	Download,
	Eye,
	MoreHorizontal,
	Move,
	PenLine,
	Trash2,
} from "lucide-react";
import React, { useCallback, useRef, useState } from "react";
import { useDrag } from "react-dnd";
import { getDocumentTypeIcon } from "@/app/dashboard/[search_space_id]/documents/(manage)/components/DocumentTypeIcon";
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
	onExport?: (doc: DocumentNodeDoc, format: string) => void;
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
	onExport,
	contextMenuOpen,
	onContextMenuOpenChange,
}: DocumentNodeProps) {
	const statusState = doc.status?.state ?? "ready";
	const isSelectable = statusState !== "pending" && statusState !== "processing";
	const isEditable =
		EDITABLE_DOCUMENT_TYPES.has(doc.document_type) &&
		statusState !== "pending" &&
		statusState !== "processing";

	const handleCheckChange = useCallback(() => {
		if (isSelectable) {
			onToggleChatMention(doc, isMentioned);
		}
	}, [doc, isMentioned, isSelectable, onToggleChatMention]);

	const [{ isDragging }, drag] = useDrag(
		() => ({
			type: DND_TYPES.DOCUMENT,
			item: { id: doc.id },
			collect: (monitor) => ({ isDragging: monitor.isDragging() }),
		}),
		[doc.id]
	);

	const isProcessing = statusState === "pending" || statusState === "processing";
	const [dropdownOpen, setDropdownOpen] = useState(false);
	const [exporting, setExporting] = useState<string | null>(null);
	const rowRef = useRef<HTMLDivElement>(null);

	const handleExport = useCallback(
		(format: string) => {
			if (!onExport) return;
			setExporting(format);
			onExport(doc, format);
			setTimeout(() => setExporting(null), 2000);
		},
		[doc, onExport]
	);

	const attachRef = useCallback(
		(node: HTMLDivElement | null) => {
			(rowRef as React.MutableRefObject<HTMLDivElement | null>).current = node;
			drag(node);
		},
		[drag]
	);

	return (
		<ContextMenu onOpenChange={onContextMenuOpenChange}>
			<ContextMenuTrigger asChild>
				{/* biome-ignore lint/a11y/useSemanticElements: contains nested interactive children (Checkbox) that render as <button>, making a semantic <button> wrapper invalid */}
				<div
					role="button"
					tabIndex={0}
					ref={attachRef}
					className={cn(
						"group flex h-8 w-full items-center gap-2.5 rounded-md px-1 text-sm hover:bg-accent/50 cursor-pointer select-none text-left",
						isMentioned && "bg-accent/30",
						isDragging && "opacity-40"
					)}
					style={{ paddingLeft: `${depth * 16 + 4}px` }}
					onClick={handleCheckChange}
					onKeyDown={(e) => {
						if (e.key === "Enter" || e.key === " ") {
							e.preventDefault();
							handleCheckChange();
						}
					}}
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
									<TooltipContent side="top">Pending — waiting to be synced</TooltipContent>
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
									<TooltipContent side="top" className="max-w-xs">
										{doc.status?.reason || "Processing failed"}
									</TooltipContent>
								</Tooltip>
							);
						}
						return (
							<Checkbox
								checked={isMentioned}
								onCheckedChange={handleCheckChange}
								onClick={(e) => e.stopPropagation()}
								className="h-3.5 w-3.5 shrink-0"
							/>
						);
					})()}

					<span className="flex-1 min-w-0 truncate">{doc.title}</span>

					<span className="shrink-0">
						{getDocumentTypeIcon(
							doc.document_type as DocumentTypeEnum,
							"h-3.5 w-3.5 text-muted-foreground"
						)}
					</span>

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
								<MoreHorizontal className="h-3.5 w-3.5" />
							</Button>
						</DropdownMenuTrigger>
						<DropdownMenuContent align="end" className="w-40" onClick={(e) => e.stopPropagation()}>
							<DropdownMenuItem onClick={() => onPreview(doc)}>
								<Eye className="mr-2 h-4 w-4" />
								Open
							</DropdownMenuItem>
							{isEditable && (
								<DropdownMenuItem onClick={() => onEdit(doc)}>
									<PenLine className="mr-2 h-4 w-4" />
									Edit
								</DropdownMenuItem>
							)}
							<DropdownMenuItem onClick={() => onMove(doc)}>
								<Move className="mr-2 h-4 w-4" />
								Move to...
							</DropdownMenuItem>
							{onExport && (
								<DropdownMenuSub>
									<DropdownMenuSubTrigger>
										<Download className="mr-2 h-4 w-4" />
										Export
									</DropdownMenuSubTrigger>
									<DropdownMenuSubContent className="min-w-[180px]">
										<ExportDropdownItems onExport={handleExport} exporting={exporting} />
									</DropdownMenuSubContent>
								</DropdownMenuSub>
							)}
							<DropdownMenuItem
								className="text-destructive focus:text-destructive"
								disabled={isProcessing}
								onClick={() => onDelete(doc)}
							>
								<Trash2 className="mr-2 h-4 w-4" />
								Delete
							</DropdownMenuItem>
						</DropdownMenuContent>
					</DropdownMenu>
				</div>
			</ContextMenuTrigger>

			{contextMenuOpen && (
				<ContextMenuContent className="w-40" onClick={(e) => e.stopPropagation()}>
					<ContextMenuItem onClick={() => onPreview(doc)}>
						<Eye className="mr-2 h-4 w-4" />
						Open
					</ContextMenuItem>
					{isEditable && (
						<ContextMenuItem onClick={() => onEdit(doc)}>
							<PenLine className="mr-2 h-4 w-4" />
							Edit
						</ContextMenuItem>
					)}
					<ContextMenuItem onClick={() => onMove(doc)}>
						<Move className="mr-2 h-4 w-4" />
						Move to...
					</ContextMenuItem>
					{onExport && (
						<ContextMenuSub>
							<ContextMenuSubTrigger>
								<Download className="mr-2 h-4 w-4" />
								Export
							</ContextMenuSubTrigger>
							<ContextMenuSubContent className="min-w-[180px]">
								<ExportContextItems onExport={handleExport} exporting={exporting} />
							</ContextMenuSubContent>
						</ContextMenuSub>
					)}
					<ContextMenuItem
						className="text-destructive focus:text-destructive"
						disabled={isProcessing}
						onClick={() => onDelete(doc)}
					>
						<Trash2 className="mr-2 h-4 w-4" />
						Delete
					</ContextMenuItem>
				</ContextMenuContent>
			)}
		</ContextMenu>
	);
});
