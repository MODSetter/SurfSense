"use client";

import { ChevronDown, ChevronRight, MessageSquare } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { CommentComposer } from "../comment-composer/comment-composer";
import { CommentItem } from "../comment-item/comment-item";
import type { CommentThreadProps } from "./types";

export function CommentThread({
	thread,
	members,
	membersLoading = false,
	onCreateReply,
	onEditComment,
	onDeleteComment,
	isSubmitting = false,
}: CommentThreadProps) {
	const [isRepliesExpanded, setIsRepliesExpanded] = useState(true);
	const [isReplyComposerOpen, setIsReplyComposerOpen] = useState(false);

	const parentComment = {
		id: thread.id,
		content: thread.content,
		contentRendered: thread.contentRendered,
		author: thread.author,
		createdAt: thread.createdAt,
		updatedAt: thread.updatedAt,
		isEdited: thread.isEdited,
		canEdit: thread.canEdit,
		canDelete: thread.canDelete,
	};

	const handleReply = () => {
		setIsReplyComposerOpen(true);
		setIsRepliesExpanded(true);
	};

	const handleReplySubmit = (content: string) => {
		onCreateReply(thread.id, content);
		setIsReplyComposerOpen(false);
	};

	const handleReplyCancel = () => {
		setIsReplyComposerOpen(false);
	};

	return (
		<div className="space-y-2">
			<CommentItem
				comment={parentComment}
				onEdit={(id) => onEditComment(id, "")}
				onDelete={onDeleteComment}
			/>

			{thread.replies.length > 1 && (
				<div className="ml-11">
					<Button
						variant="ghost"
						size="sm"
						className="h-7 px-2 text-xs text-muted-foreground hover:text-foreground"
						onClick={() => setIsRepliesExpanded(!isRepliesExpanded)}
					>
						{isRepliesExpanded ? (
							<ChevronDown className="mr-1 size-3" />
						) : (
							<ChevronRight className="mr-1 size-3" />
						)}
						{thread.replies.length} replies
					</Button>
				</div>
			)}

			{thread.replies.length > 0 && (thread.replies.length === 1 || isRepliesExpanded) && (
				<div className="ml-11 space-y-3">
					{thread.replies.map((reply) => (
						<CommentItem
							key={reply.id}
							comment={reply}
							isReply
							onEdit={(id) => onEditComment(id, "")}
							onDelete={onDeleteComment}
						/>
					))}
				</div>
			)}

			<div className="ml-11">
				{isReplyComposerOpen ? (
					<CommentComposer
						members={members}
						membersLoading={membersLoading}
						placeholder="Write a reply..."
						submitLabel="Reply"
						isSubmitting={isSubmitting}
						onSubmit={handleReplySubmit}
						onCancel={handleReplyCancel}
						autoFocus
					/>
				) : (
					<Button variant="outline" size="sm" className="h-7 px-3 text-xs" onClick={handleReply}>
						<MessageSquare className="mr-1.5 size-3" />
						Reply
					</Button>
				)}
			</div>
		</div>
	);
}
