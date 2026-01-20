export interface MemberOption {
	id: string;
	displayName: string | null;
	email: string;
	avatarUrl?: string | null;
}

export interface MemberMentionPickerProps {
	members: MemberOption[];
	query: string;
	highlightedIndex: number;
	isLoading?: boolean;
	onSelect: (member: MemberOption) => void;
	onHighlightChange: (index: number) => void;
}

export interface MemberMentionItemProps {
	member: MemberOption;
	isHighlighted: boolean;
	onSelect: (member: MemberOption) => void;
	onMouseEnter: () => void;
}
