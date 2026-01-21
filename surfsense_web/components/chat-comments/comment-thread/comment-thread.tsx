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
	const [editingCommentId, setEditingCommentId] = useState<number | null>(null);

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

	const handleEditStart = (commentId: number) => {
		setEditingCommentId(commentId);
	};

	const handleEditSubmit = (commentId: number, content: string) => {
		onEditComment(commentId, content);
		setEditingCommentId(null);
	};

	const handleEditCancel = () => {
		setEditingCommentId(null);
	};

	const hasReplies = thread.replies.length > 0;
	const showReplies = thread.replies.length === 1 || isRepliesExpanded;

	return (
		<div>
			{/* Parent comment */}
			<CommentItem
				comment={parentComment}
				onEdit={handleEditStart}
				onEditSubmit={handleEditSubmit}
				onEditCancel={handleEditCancel}
				onDelete={onDeleteComment}
				isEditing={editingCommentId === parentComment.id}
				isSubmitting={isSubmitting}
				members={members}
				membersLoading={membersLoading}
			/>

			{/* Replies and actions - using flex layout with connector */}
			{(hasReplies || isReplyComposerOpen) && (
				<div className="flex">
					{/* Connector column - vertical line */}
					<div className="flex w-7 flex-col items-center">
						<div className="w-px flex-1 bg-border" />
					</div>

					{/* Content column */}
					<div className="min-w-0 flex-1 space-y-2 pb-1">
						{/* Expand/collapse for multiple replies */}
						{thread.replies.length > 1 && (
							<Button
								variant="ghost"
								size="sm"
								className="h-6 px-2 text-xs text-muted-foreground hover:text-foreground"
								onClick={() => setIsRepliesExpanded(!isRepliesExpanded)}
							>
								{isRepliesExpanded ? (
									<ChevronDown className="mr-1 size-3" />
								) : (
									<ChevronRight className="mr-1 size-3" />
								)}
								{thread.replies.length} replies
							</Button>
						)}

						{/* Reply items */}
						{showReplies && hasReplies && (
							<div className="space-y-3 pt-2">
								{thread.replies.map((reply) => (
									<CommentItem
										key={reply.id}
										comment={reply}
										isReply
										onEdit={handleEditStart}
										onEditSubmit={handleEditSubmit}
										onEditCancel={handleEditCancel}
										onDelete={onDeleteComment}
										isEditing={editingCommentId === reply.id}
										isSubmitting={isSubmitting}
										members={members}
										membersLoading={membersLoading}
									/>
								))}
							</div>
						)}

						{/* Reply composer or button */}

						{isReplyComposerOpen ? (
							<div className="pt-3">
								<CommentComposer
									members={members}
									membersLoading={membersLoading}
									placeholder="Reply or @mention"
									submitLabel="Reply"
									isSubmitting={isSubmitting}
									onSubmit={handleReplySubmit}
									onCancel={handleReplyCancel}
									autoFocus
								/>
							</div>
						) : (
							<Button variant="ghost" size="sm" className="h-7 px-2 text-xs" onClick={handleReply}>
								<MessageSquare className="mr-1 size-3" />
								Reply
							</Button>
						)}
					</div>
				</div>
			)}

			{/* Reply button when no replies yet */}
			{!hasReplies && !isReplyComposerOpen && (
				<div className="ml-7 mt-1">
					<Button variant="ghost" size="sm" className="h-7 px-2 text-xs" onClick={handleReply}>
						<MessageSquare className="mr-1 size-3" />
						Reply
					</Button>
				</div>
			)}
		</div>
	);
}
