"use client";

import { cn } from "@/lib/utils";
import { CommentComposer } from "../comment-composer/comment-composer";
import { CommentThread } from "../comment-thread/comment-thread";
import type { CommentPanelProps } from "./types";

export function CommentPanel({
	threads,
	members,
	membersLoading = false,
	isLoading = false,
	onCreateComment,
	onCreateReply,
	onEditComment,
	onDeleteComment,
	isSubmitting = false,
	maxHeight,
	variant = "desktop",
}: CommentPanelProps) {
	const handleCommentSubmit = (content: string) => {
		onCreateComment(content);
	};

	const isMobile = variant === "mobile";
	const isInline = variant === "inline";

	if (isLoading) {
		return (
			<div
				className={cn(
					"flex min-h-[120px] items-center justify-center p-4",
					isInline &&
						"w-full rounded-xl border-sidebar-border border bg-sidebar text-sidebar-foreground shadow-lg",
					!isMobile &&
						!isInline &&
						"w-96 rounded-lg border-sidebar-border border bg-sidebar text-sidebar-foreground"
				)}
			>
				<div className="flex items-center gap-2 text-sm text-muted-foreground">
					<div className="size-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
					Loading comments...
				</div>
			</div>
		);
	}

	const hasThreads = threads.length > 0;

	// Ensure minimum usable height for empty state + composer button
	const minHeight = 180;
	const effectiveMaxHeight = maxHeight ? Math.max(maxHeight, minHeight) : undefined;

	return (
		<div
			className={cn(
				"flex flex-col",
				isMobile && "w-full",
				isInline &&
					"w-full rounded-xl border-sidebar-border border bg-sidebar text-sidebar-foreground shadow-lg max-h-80",
				!isMobile &&
					!isInline &&
					"w-85 rounded-lg border-sidebar-border border bg-sidebar text-sidebar-foreground"
			)}
			style={
				!isMobile && !isInline && effectiveMaxHeight ? { maxHeight: effectiveMaxHeight } : undefined
			}
		>
			{hasThreads && (
				<div className={cn("min-h-0 flex-1 overflow-y-auto scrollbar-thin", isMobile && "pb-24")}>
					<div className="space-y-4 p-4">
						{threads.map((thread) => (
							<CommentThread
								key={thread.id}
								thread={thread}
								members={members}
								membersLoading={membersLoading}
								onCreateReply={onCreateReply}
								onEditComment={onEditComment}
								onDeleteComment={onDeleteComment}
								isSubmitting={isSubmitting}
							/>
						))}
					</div>
				</div>
			)}

			<div className={cn("p-3", isMobile && "fixed bottom-0 left-0 right-0 z-50 bg-card border-t")}>
				<CommentComposer
					members={members}
					membersLoading={membersLoading}
					placeholder="Comment or @mention"
					submitLabel="Comment"
					isSubmitting={isSubmitting}
					onSubmit={handleCommentSubmit}
					autoFocus={!hasThreads}
					compact
				/>
			</div>
		</div>
	);
}
