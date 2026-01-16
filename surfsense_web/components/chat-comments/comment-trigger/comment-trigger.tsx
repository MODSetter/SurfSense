"use client";

import { MessageSquare } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { CommentTriggerProps } from "./types";

export function CommentTrigger({ commentCount, isOpen, onClick }: CommentTriggerProps) {
	const hasComments = commentCount > 0;

	return (
		<Button
			variant={isOpen ? "secondary" : "ghost"}
			size="sm"
			className={cn(
				"h-8 gap-1.5 px-2 transition-opacity",
				isOpen ? "text-foreground" : "text-muted-foreground",
				!hasComments && !isOpen && "opacity-0 group-hover:opacity-100"
			)}
			onClick={onClick}
		>
			<MessageSquare className={cn("size-4", isOpen && "fill-current")} />
			{hasComments && (
				<span className="min-w-[1.25rem] text-xs font-medium">{commentCount}</span>
			)}
		</Button>
	);
}

