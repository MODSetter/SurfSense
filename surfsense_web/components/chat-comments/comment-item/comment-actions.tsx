"use client";

import { MoreHorizontal, Pencil, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuSeparator,
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
					className="size-7 opacity-100 md:opacity-0 md:group-hover:opacity-100 transition-opacity"
				>
					<MoreHorizontal className="size-4 text-muted-foreground" />
				</Button>
			</DropdownMenuTrigger>
			<DropdownMenuContent align="end">
				{canEdit && (
					<DropdownMenuItem onClick={onEdit}>
						<Pencil className="mr-2 size-4" />
						Edit
					</DropdownMenuItem>
				)}
				{canEdit && canDelete && <DropdownMenuSeparator />}
				{canDelete && (
					<DropdownMenuItem onClick={onDelete} className="text-destructive focus:text-destructive">
						<Trash2 className="mr-2 size-4" />
						Delete
					</DropdownMenuItem>
				)}
			</DropdownMenuContent>
		</DropdownMenu>
	);
}
