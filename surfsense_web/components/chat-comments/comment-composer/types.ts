import type { MemberOption } from "../member-mention-picker/types";

export interface CommentComposerProps {
	members: MemberOption[];
	membersLoading?: boolean;
	placeholder?: string;
	submitLabel?: string;
	isSubmitting?: boolean;
	onSubmit: (content: string) => void;
	onCancel?: () => void;
	autoFocus?: boolean;
	initialValue?: string;
}

export interface MentionState {
	isActive: boolean;
	query: string;
	startIndex: number;
}

export interface InsertedMention {
	id: string;
	displayName: string;
}
