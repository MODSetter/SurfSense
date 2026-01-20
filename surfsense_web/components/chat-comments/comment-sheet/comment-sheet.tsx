"use client";

import { MessageSquare } from "lucide-react";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { cn } from "@/lib/utils";
import { CommentPanelContainer } from "../comment-panel-container/comment-panel-container";
import type { CommentSheetProps } from "./types";

export function CommentSheet({
	messageId,
	isOpen,
	onOpenChange,
	commentCount = 0,
	side = "bottom",
}: CommentSheetProps) {
	const isBottomSheet = side === "bottom";

	return (
		<Sheet open={isOpen} onOpenChange={onOpenChange}>
			<SheetContent
				side={side}
				className={cn(
					"flex flex-col p-0",
					isBottomSheet ? "h-[85vh] max-h-[85vh] rounded-t-xl" : "h-full w-full max-w-md"
				)}
			>
				{/* Drag handle indicator - only for bottom sheet */}
				{isBottomSheet && (
					<div className="flex justify-center pt-3 pb-1">
						<div className="h-1 w-10 rounded-full bg-muted-foreground/30" />
					</div>
				)}
				<SheetHeader className={cn("flex-shrink-0 border-b px-4", isBottomSheet ? "pb-3" : "py-4")}>
					<SheetTitle className="flex items-center gap-2 text-base font-semibold">
						<MessageSquare className="size-5" />
						Comments
						{commentCount > 0 && (
							<span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
								{commentCount}
							</span>
						)}
					</SheetTitle>
				</SheetHeader>
				<div className="min-h-0 flex-1 overflow-y-auto">
					<CommentPanelContainer messageId={messageId} isOpen={true} variant="mobile" />
				</div>
			</SheetContent>
		</Sheet>
	);
}
