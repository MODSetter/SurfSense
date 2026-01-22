"use client";

import { MessageSquare } from "lucide-react";
import {
	Drawer,
	DrawerContent,
	DrawerHandle,
	DrawerHeader,
	DrawerTitle,
} from "@/components/ui/drawer";
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

	// Use Drawer for mobile (bottom), Sheet for medium screens (right)
	if (isBottomSheet) {
		return (
			<Drawer open={isOpen} onOpenChange={onOpenChange} shouldScaleBackground={false}>
				<DrawerContent className="h-[85vh] max-h-[85vh] z-80" overlayClassName="z-80">
					<DrawerHandle />
					<DrawerHeader className="px-4 pb-3 pt-2">
						<DrawerTitle className="flex items-center gap-2 text-base font-semibold">
							<MessageSquare className="size-5" />
							Comments
							{commentCount > 0 && (
								<span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
									{commentCount}
								</span>
							)}
						</DrawerTitle>
					</DrawerHeader>
					<div className="min-h-0 flex-1 overflow-y-auto scrollbar-thin">
						<CommentPanelContainer messageId={messageId} isOpen={true} variant="mobile" />
					</div>
				</DrawerContent>
			</Drawer>
		);
	}

	// Use Sheet for medium screens (right side)
	return (
		<Sheet open={isOpen} onOpenChange={onOpenChange}>
			<SheetContent
				side={side}
				className={cn("flex flex-col gap-0 overflow-hidden p-0 h-full w-full max-w-md")}
			>
				<SheetHeader className="flex-shrink-0 px-4 py-4">
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
				<div className="min-h-0 flex-1 overflow-y-auto scrollbar-thin">
					<CommentPanelContainer messageId={messageId} isOpen={true} variant="mobile" />
				</div>
			</SheetContent>
		</Sheet>
	);
}
