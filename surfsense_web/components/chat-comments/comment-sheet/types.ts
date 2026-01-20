export interface CommentSheetProps {
	messageId: number;
	isOpen: boolean;
	onOpenChange: (open: boolean) => void;
	commentCount?: number;
	/** Side to open the sheet from - bottom for mobile, right for medium screens */
	side?: "bottom" | "right";
}
