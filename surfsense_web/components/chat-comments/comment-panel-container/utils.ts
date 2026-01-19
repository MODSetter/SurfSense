import type { Comment, CommentReply } from "@/contracts/types/chat-comments.types";
import type { Membership } from "@/contracts/types/members.types";
import type { CommentData } from "../comment-item/types";
import type { CommentThreadData } from "../comment-thread/types";
import type { MemberOption } from "../member-mention-picker/types";

export function transformAuthor(author: Comment["author"]): CommentData["author"] {
	if (!author) return null;
	return {
		id: author.id,
		displayName: author.display_name,
		email: author.email,
		avatarUrl: author.avatar_url,
	};
}

export function transformReply(reply: CommentReply): CommentData {
	return {
		id: reply.id,
		content: reply.content,
		contentRendered: reply.content_rendered,
		author: transformAuthor(reply.author),
		createdAt: reply.created_at,
		updatedAt: reply.updated_at,
		isEdited: reply.is_edited,
		canEdit: reply.can_edit,
		canDelete: reply.can_delete,
	};
}

export function transformComment(comment: Comment): CommentThreadData {
	return {
		id: comment.id,
		messageId: comment.message_id,
		content: comment.content,
		contentRendered: comment.content_rendered,
		author: transformAuthor(comment.author),
		createdAt: comment.created_at,
		updatedAt: comment.updated_at,
		isEdited: comment.is_edited,
		canEdit: comment.can_edit,
		canDelete: comment.can_delete,
		replyCount: comment.reply_count,
		replies: comment.replies.map(transformReply),
	};
}

export function transformMember(membership: Membership): MemberOption {
	return {
		id: membership.user_id,
		displayName: membership.user_display_name ?? null,
		email: membership.user_email ?? "",
		avatarUrl: membership.user_avatar_url ?? null,
	};
}
