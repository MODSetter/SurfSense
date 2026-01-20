import type { CommentThreadData } from "../comment-thread/types";
import type { MemberOption } from "../member-mention-picker/types";

export interface CommentPanelProps {
	threads: CommentThreadData[];
	members: MemberOption[];
	membersLoading?: boolean;
	isLoading?: boolean;
	onCreateComment: (content: string) => void;
	onCreateReply: (commentId: number, content: string) => void;
	onEditComment: (commentId: number, content: string) => void;
	onDeleteComment: (commentId: number) => void;
	isSubmitting?: boolean;
	maxHeight?: number;
	/** Variant for responsive styling - desktop shows border/bg, mobile is plain */
	variant?: "desktop" | "mobile";
}
