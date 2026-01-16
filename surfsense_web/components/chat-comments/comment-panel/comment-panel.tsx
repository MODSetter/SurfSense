"use client";

import { MessageSquarePlus } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
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
	maxHeight = 400,
}: CommentPanelProps) {
	const [isComposerOpen, setIsComposerOpen] = useState(false);

	const handleCommentSubmit = (content: string) => {
		onCreateComment(content);
		setIsComposerOpen(false);
	};

	const handleComposerCancel = () => {
		setIsComposerOpen(false);
	};

	if (isLoading) {
		return (
			<div className="flex min-h-[120px] w-96 items-center justify-center rounded-lg border bg-card p-4">
				<div className="flex items-center gap-2 text-sm text-muted-foreground">
					<div className="size-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
					Loading comments...
				</div>
			</div>
		);
	}

	const hasThreads = threads.length > 0;
	const showEmptyState = !hasThreads && !isComposerOpen;

	return (
		<div className="flex w-70 flex-col rounded-lg border bg-card">
			{hasThreads && (
				<div
					className="overflow-y-auto"
					style={{ maxHeight }}
				>
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

			{showEmptyState && (
				<div className="flex min-h-[120px] flex-col items-center justify-center gap-2 p-4 text-center">
					<MessageSquarePlus className="size-8 text-muted-foreground/50" />
					<p className="text-sm text-muted-foreground">No comments yet</p>
					<p className="text-xs text-muted-foreground/70">
						Start a conversation about this response
					</p>
				</div>
			)}

			<div className={showEmptyState ? "border-t p-3" : "p-3"}>
				{isComposerOpen ? (
					<CommentComposer
						members={members}
						membersLoading={membersLoading}
						placeholder="Write a comment..."
						submitLabel="Comment"
						isSubmitting={isSubmitting}
						onSubmit={handleCommentSubmit}
						onCancel={handleComposerCancel}
						autoFocus
					/>
				) : (
					<Button
						variant="ghost"
						className="w-full justify-start text-muted-foreground hover:text-foreground"
						onClick={() => setIsComposerOpen(true)}
					>
						<MessageSquarePlus className="mr-2 size-4" />
						Add a comment...
					</Button>
				)}
			</div>
		</div>
	);
}
