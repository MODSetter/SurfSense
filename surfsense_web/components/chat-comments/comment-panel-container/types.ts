export interface CommentPanelContainerProps {
	messageId: number;
	isOpen: boolean;
	maxHeight?: number;
	/** Variant for responsive styling - desktop shows border/bg, mobile is plain */
	variant?: "desktop" | "mobile";
}
