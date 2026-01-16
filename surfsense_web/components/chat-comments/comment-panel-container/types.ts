export interface CommentPanelContainerProps {
	messageId: number;
	searchSpaceId: number;
	isOpen: boolean;
	onClose?: () => void;
	maxHeight?: number;
}

