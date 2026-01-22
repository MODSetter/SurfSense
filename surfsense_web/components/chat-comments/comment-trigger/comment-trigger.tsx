"use client";

import { MessageSquarePlus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { CommentTriggerProps } from "./types";

export function CommentTrigger({ commentCount, isOpen, onClick, disabled }: CommentTriggerProps) {
	const hasComments = commentCount > 0;

	return (
		<Button
			variant={hasComments ? "outline" : isOpen ? "secondary" : "ghost"}
			size="icon"
			disabled={disabled}
			className={cn(
				"relative size-10 rounded-full transition-all duration-200",
				hasComments
					? "border-primary/50 bg-primary/5 text-primary hover:bg-primary/10 hover:border-primary"
					: isOpen
						? "text-foreground"
						: "text-muted-foreground hover:text-foreground",
				!hasComments && !isOpen && "opacity-0 group-hover:opacity-100",
				disabled && "cursor-not-allowed opacity-50"
			)}
			onClick={onClick}
		>
			<MessageSquarePlus className={cn("size-5", (hasComments || isOpen) && "fill-current")} />
			{hasComments && (
				<span className="absolute -top-1 -right-1 flex size-5 items-center justify-center rounded-full bg-primary text-[10px] font-bold text-primary-foreground">
					{commentCount > 9 ? "9+" : commentCount}
				</span>
			)}
		</Button>
	);
}
