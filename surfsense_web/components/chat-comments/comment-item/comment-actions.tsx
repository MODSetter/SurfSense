"use client";

import { MoreHorizontal, PenLine, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { CommentActionsProps } from "./types";

export function CommentActions({ canEdit, canDelete, onEdit, onDelete }: CommentActionsProps) {
	if (!canEdit && !canDelete) {
		return null;
	}

	return (
		<DropdownMenu>
			<DropdownMenuTrigger asChild>
				<Button
					variant="ghost"
					size="icon"
					className="size-7 text-muted-foreground opacity-100 md:opacity-0 md:group-hover:opacity-100 transition-opacity"
				>
					<MoreHorizontal className="size-4" />
				</Button>
			</DropdownMenuTrigger>
			<DropdownMenuContent align="end">
				{canEdit && (
					<DropdownMenuItem onClick={onEdit}>
						<PenLine className="mr-2 size-4" />
						Edit
					</DropdownMenuItem>
				)}
				{canDelete && (
					<DropdownMenuItem onClick={onDelete}>
						<Trash2 className="mr-2 size-4" />
						Delete
					</DropdownMenuItem>
				)}
			</DropdownMenuContent>
		</DropdownMenu>
	);
}
