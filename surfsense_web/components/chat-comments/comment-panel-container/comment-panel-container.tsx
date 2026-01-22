"use client";

import { useAtom } from "jotai";
import { useMemo } from "react";
import {
	createCommentMutationAtom,
	createReplyMutationAtom,
	deleteCommentMutationAtom,
	updateCommentMutationAtom,
} from "@/atoms/chat-comments/comments-mutation.atoms";
import { membersAtom } from "@/atoms/members/members-query.atoms";
import { currentUserAtom } from "@/atoms/user/user-query.atoms";
import { useComments } from "@/hooks/use-comments";
import { CommentPanel } from "../comment-panel/comment-panel";
import type { CommentPanelContainerProps } from "./types";
import { transformComment, transformMember } from "./utils";

export function CommentPanelContainer({
	messageId,
	isOpen,
	maxHeight,
	variant = "desktop",
}: CommentPanelContainerProps) {
	const { data: commentsData, isLoading: isCommentsLoading } = useComments({
		messageId,
		enabled: isOpen,
	});

	const [{ data: membersData, isLoading: isMembersLoading }] = useAtom(membersAtom);
	const [{ data: currentUser }] = useAtom(currentUserAtom);

	const [{ mutate: createComment, isPending: isCreating }] = useAtom(createCommentMutationAtom);
	const [{ mutate: createReply, isPending: isCreatingReply }] = useAtom(createReplyMutationAtom);
	const [{ mutate: updateComment, isPending: isUpdating }] = useAtom(updateCommentMutationAtom);
	const [{ mutate: deleteComment, isPending: isDeleting }] = useAtom(deleteCommentMutationAtom);

	const commentThreads = useMemo(() => {
		if (!commentsData?.comments) return [];
		return commentsData.comments.map(transformComment);
	}, [commentsData]);

	const members = useMemo(() => {
		if (!membersData) return [];
		const allMembers = membersData.map(transformMember);
		// Filter out current user from mention picker
		if (currentUser?.id) {
			return allMembers.filter((member) => member.id !== currentUser.id);
		}
		return allMembers;
	}, [membersData, currentUser?.id]);

	const isSubmitting = isCreating || isCreatingReply || isUpdating || isDeleting;

	const handleCreateComment = (content: string) => {
		createComment({ message_id: messageId, content });
	};

	const handleCreateReply = (commentId: number, content: string) => {
		createReply({ comment_id: commentId, content, message_id: messageId });
	};

	const handleEditComment = (commentId: number, content: string) => {
		updateComment({ comment_id: commentId, content, message_id: messageId });
	};

	const handleDeleteComment = (commentId: number) => {
		deleteComment({ comment_id: commentId, message_id: messageId });
	};

	if (!isOpen) return null;

	return (
		<CommentPanel
			threads={commentThreads}
			members={members}
			membersLoading={isMembersLoading}
			isLoading={isCommentsLoading}
			onCreateComment={handleCreateComment}
			onCreateReply={handleCreateReply}
			onEditComment={handleEditComment}
			onDeleteComment={handleDeleteComment}
			isSubmitting={isSubmitting}
			maxHeight={maxHeight}
			variant={variant}
		/>
	);
}
