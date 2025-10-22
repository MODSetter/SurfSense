import ChatPanelView from "./ChatPanelView";

interface ChatPanelContainerProps {
	chatId: string;
}

export function ChatPanelContainer({ chatId }: ChatPanelContainerProps) {
	return <ChatPanelView chatId={chatId} />;
}
