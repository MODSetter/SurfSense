export interface CommentAuthor {
	id: string;
	displayName: string | null;
	email: string;
	avatarUrl?: string | null;
}

export interface CommentData {
	id: number;
	content: string;
	contentRendered: string;
	author: CommentAuthor | null;
	createdAt: string;
	updatedAt: string;
	isEdited: boolean;
	canEdit: boolean;
	canDelete: boolean;
}

export interface CommentItemProps {
	comment: CommentData;
	onEdit?: (commentId: number) => void;
	onEditSubmit?: (commentId: number, content: string) => void;
	onEditCancel?: () => void;
	onDelete?: (commentId: number) => void;
	onReply?: (commentId: number) => void;
	isReply?: boolean;
	isEditing?: boolean;
	isSubmitting?: boolean;
	members?: Array<{
		id: string;
		displayName: string | null;
		email: string;
		avatarUrl?: string | null;
	}>;
	membersLoading?: boolean;
}

export interface CommentActionsProps {
	canEdit: boolean;
	canDelete: boolean;
	onEdit: () => void;
	onDelete: () => void;
}
