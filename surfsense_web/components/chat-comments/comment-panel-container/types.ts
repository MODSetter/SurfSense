export interface CommentPanelContainerProps {
	messageId: number;
	isOpen: boolean;
	maxHeight?: number;
	/** Variant for responsive styling - desktop shows border/bg, mobile is plain, inline fits within message width */
	variant?: "desktop" | "mobile" | "inline";
}
