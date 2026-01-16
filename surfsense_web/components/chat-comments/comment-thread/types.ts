import type { CommentData } from "../comment-item/types";
import type { MemberOption } from "../member-mention-picker/types";

export interface CommentThreadData {
	id: number;
	messageId: number;
	content: string;
	contentRendered: string;
	author: CommentData["author"];
	createdAt: string;
	updatedAt: string;
	isEdited: boolean;
	canEdit: boolean;
	canDelete: boolean;
	replyCount: number;
	replies: CommentData[];
}

export interface CommentThreadProps {
	thread: CommentThreadData;
	members: MemberOption[];
	membersLoading?: boolean;
	onCreateReply: (commentId: number, content: string) => void;
	onEditComment: (commentId: number, content: string) => void;
	onDeleteComment: (commentId: number) => void;
	isSubmitting?: boolean;
}
