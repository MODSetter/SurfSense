"use client";

import { type ChatHandler, ChatSection as LlamaIndexChatSection } from "@llamaindex/chat-ui";
import { useSetAtom } from "jotai";
import { useParams } from "next/navigation";
import { useEffect } from "react";
import { ChatInputUI } from "@/components/chat/ChatInputGroup";
import { ChatMessagesUI } from "@/components/chat/ChatMessages";
import type { Document } from "@/hooks/use-documents";
import { activeChatIdAtom } from "@/stores/chats/active-chat.atom";
import { ChatPanelContainer } from "./ChatPanel/ChatPanelContainer";

interface ChatInterfaceProps {
	handler: ChatHandler;
	onDocumentSelectionChange?: (documents: Document[]) => void;
	selectedDocuments?: Document[];
	onConnectorSelectionChange?: (connectorTypes: string[]) => void;
	selectedConnectors?: string[];
	searchMode?: "DOCUMENTS" | "CHUNKS";
	onSearchModeChange?: (mode: "DOCUMENTS" | "CHUNKS") => void;
	topK?: number;
	onTopKChange?: (topK: number) => void;
}

export default function ChatInterface({
	handler,
	onDocumentSelectionChange,
	selectedDocuments = [],
	onConnectorSelectionChange,
	selectedConnectors = [],
	searchMode,
	onSearchModeChange,
	topK = 10,
	onTopKChange,
}: ChatInterfaceProps) {
	const { chat_id, search_space_id } = useParams();
	const setActiveChatIdState = useSetAtom(activeChatIdAtom);

	useEffect(() => {
		const id = typeof chat_id === "string" ? chat_id : chat_id ? chat_id[0] : "";
		if (!id) return;
		setActiveChatIdState(id);
	}, [chat_id, search_space_id]);

	return (
		<LlamaIndexChatSection handler={handler} className="flex h-full max-w-7xl mx-auto">
			<div className="flex grow-1 flex-col">
				<ChatMessagesUI />
				<div className="border-1 rounded-4xl p-2">
					<ChatInputUI
						onDocumentSelectionChange={onDocumentSelectionChange}
						selectedDocuments={selectedDocuments}
						onConnectorSelectionChange={onConnectorSelectionChange}
						selectedConnectors={selectedConnectors}
						searchMode={searchMode}
						onSearchModeChange={onSearchModeChange}
						topK={topK}
						onTopKChange={onTopKChange}
					/>
				</div>
			</div>
		</LlamaIndexChatSection>
	);
}
