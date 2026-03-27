"use client";

import {
	Eye,
	MoreHorizontal,
	Move,
	Pencil,
	Trash2,
} from "lucide-react";
import React, { useCallback, useRef } from "react";
import { useDrag } from "react-dnd";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
	ContextMenu,
	ContextMenuContent,
	ContextMenuItem,
	ContextMenuSeparator,
	ContextMenuTrigger,
} from "@/components/ui/context-menu";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuSeparator,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { getDocumentTypeIcon } from "@/app/dashboard/[search_space_id]/documents/(manage)/components/DocumentTypeIcon";
import type { DocumentTypeEnum } from "@/contracts/types/document.types";
import { cn } from "@/lib/utils";
import { DND_TYPES } from "./FolderNode";

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
}: DocumentNodeProps) {
	const statusState = doc.status?.state ?? "ready";
	const isSelectable = statusState !== "pending" && statusState !== "processing";
	const isEditable =
		doc.document_type === "NOTE" &&
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
		[doc.id],
	);

	const isProcessing = statusState === "pending" || statusState === "processing";

	return (
		<ContextMenu>
			<ContextMenuTrigger asChild>
				<div
					ref={drag}
					className={cn(
						"group flex h-8 items-center gap-1.5 rounded-md px-1 text-sm hover:bg-accent/50 cursor-pointer select-none",
						isMentioned && "bg-accent/30",
						isDragging && "opacity-40",
					)}
					style={{ paddingLeft: `${depth * 16 + 4}px` }}
					onClick={handleCheckChange}
				>
					{isSelectable ? (
						<Checkbox
							checked={isMentioned}
							onCheckedChange={handleCheckChange}
							onClick={(e) => e.stopPropagation()}
							className="h-3.5 w-3.5 shrink-0"
						/>
					) : (
						<span className="flex h-3.5 w-3.5 shrink-0 items-center justify-center">
							<span
								className={cn(
									"h-2 w-2 rounded-full",
									statusState === "processing" && "animate-pulse bg-amber-500",
									statusState === "pending" && "bg-muted-foreground/40",
									statusState === "failed" && "bg-destructive",
								)}
							/>
						</span>
					)}

					<span className="flex-1 min-w-0 truncate">{doc.title}</span>

					<span className="shrink-0">
						{getDocumentTypeIcon(doc.document_type as DocumentTypeEnum, "h-3.5 w-3.5 text-muted-foreground")}
					</span>

					<DropdownMenu>
						<DropdownMenuTrigger asChild>
							<Button
								variant="ghost"
								size="icon"
								className="h-6 w-6 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity"
								onClick={(e) => e.stopPropagation()}
							>
								<MoreHorizontal className="h-3.5 w-3.5" />
							</Button>
						</DropdownMenuTrigger>
						<DropdownMenuContent align="end" className="w-44">
							<DropdownMenuItem onClick={() => onPreview(doc)}>
								<Eye className="mr-2 h-4 w-4" />
								Preview
							</DropdownMenuItem>
							{isEditable && (
								<DropdownMenuItem onClick={() => onEdit(doc)}>
									<Pencil className="mr-2 h-4 w-4" />
									Edit
								</DropdownMenuItem>
							)}
							<DropdownMenuItem onClick={() => onMove(doc)}>
								<Move className="mr-2 h-4 w-4" />
								Move to...
							</DropdownMenuItem>
							<DropdownMenuSeparator />
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

			<ContextMenuContent className="w-44">
				<ContextMenuItem onClick={() => onPreview(doc)}>
					<Eye className="mr-2 h-4 w-4" />
					Preview
				</ContextMenuItem>
				{isEditable && (
					<ContextMenuItem onClick={() => onEdit(doc)}>
						<Pencil className="mr-2 h-4 w-4" />
						Edit
					</ContextMenuItem>
				)}
				<ContextMenuItem onClick={() => onMove(doc)}>
					<Move className="mr-2 h-4 w-4" />
					Move to...
				</ContextMenuItem>
				<ContextMenuSeparator />
				<ContextMenuItem
					className="text-destructive focus:text-destructive"
					disabled={isProcessing}
					onClick={() => onDelete(doc)}
				>
					<Trash2 className="mr-2 h-4 w-4" />
					Delete
				</ContextMenuItem>
			</ContextMenuContent>
		</ContextMenu>
	);
});
