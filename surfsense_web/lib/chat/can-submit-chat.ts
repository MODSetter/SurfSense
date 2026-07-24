export interface CanSubmitChatInput {
	isLoadingMessages: boolean;
	isThreadRunning: boolean;
	isBlockedByOtherUser: boolean;
	isComposerEmpty: boolean;
	isWorkspaceChatReady: boolean;
}

export function canSubmitChat({
	isLoadingMessages,
	isThreadRunning,
	isBlockedByOtherUser,
	isComposerEmpty,
	isWorkspaceChatReady,
}: CanSubmitChatInput): boolean {
	return (
		!isLoadingMessages &&
		!isThreadRunning &&
		!isBlockedByOtherUser &&
		!isComposerEmpty &&
		isWorkspaceChatReady
	);
}
