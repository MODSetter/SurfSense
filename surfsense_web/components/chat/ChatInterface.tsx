"use client";

import { type ChatHandler, ChatSection as LlamaIndexChatSection } from "@llamaindex/chat-ui";
import { useParams } from "next/navigation";
import { createContext, useCallback, useEffect, useState } from "react";
import type { ChatDetails } from "@/app/dashboard/[search_space_id]/chats/chats-client";
import type { PodcastItem } from "@/app/dashboard/[search_space_id]/podcasts/podcasts-client";
import type { ResearchMode } from "@/components/chat";
import { ChatInputUI } from "@/components/chat/ChatInputGroup";
import { ChatMessagesUI } from "@/components/chat/ChatMessages";
import { useChatAPI } from "@/hooks/use-chat";
import type { Document } from "@/hooks/use-documents";
import { ChatPanelContainer } from "./ChatPanel/ChatPanelContainer";

interface ChatInterfaceProps {
	handler: ChatHandler;
	onDocumentSelectionChange?: (documents: Document[]) => void;
	selectedDocuments?: Document[];
	onConnectorSelectionChange?: (connectorTypes: string[]) => void;
	selectedConnectors?: string[];
	searchMode?: "DOCUMENTS" | "CHUNKS";
	onSearchModeChange?: (mode: "DOCUMENTS" | "CHUNKS") => void;
}

interface ChatInterfaceContext {
	isChatPannelOpen: boolean;
	setIsChatPannelOpen: (value: boolean) => void;
	chat_id: string;
	chatDetails: ChatDetails | null;
}

export const chatInterfaceContext = createContext<ChatInterfaceContext | null>(null);

export default function ChatInterface({
	handler,
	onDocumentSelectionChange,
	selectedDocuments = [],
	onConnectorSelectionChange,
	selectedConnectors = [],
	searchMode,
	onSearchModeChange,
}: ChatInterfaceProps) {
	const { chat_id, search_space_id } = useParams();
	const [chatDetails, setChatDetails] = useState<ChatDetails | null>(null);
	const [isChatPannelOpen, setIsChatPannelOpen] = useState(false);
	const [podcast, setPodcast] = useState<PodcastItem | null>(null);
	const contextValue = {
		isChatPannelOpen,
		setIsChatPannelOpen,
		chat_id: typeof chat_id === "string" ? chat_id : chat_id ? chat_id[0] : "",
		podcast,
		setPodcast,
		chatDetails,
	};

	const { fetchChatDetails } = useChatAPI({
		token: localStorage.getItem("surfsense_bearer_token"),
		search_space_id: search_space_id as string,
	});

	const getChat = useCallback(
		async (id: string) => {
			const chat = await fetchChatDetails(id);
			setChatDetails(chat);
		},
		[fetchChatDetails]
	);

	useEffect(() => {
		const id = typeof chat_id === "string" ? chat_id : chat_id ? chat_id[0] : "";
		if (!id) return;
		getChat(id);
	}, [chat_id, search_space_id]);

	return (
		<chatInterfaceContext.Provider value={contextValue}>
			<LlamaIndexChatSection handler={handler} className="flex h-full">
				<div className="flex gap-4 flex-1 w-full">
					<div className="flex grow-1 flex-col">
						<ChatMessagesUI />
						<div className="border-t p-4">
							<ChatInputUI
								onDocumentSelectionChange={onDocumentSelectionChange}
								selectedDocuments={selectedDocuments}
								onConnectorSelectionChange={onConnectorSelectionChange}
								selectedConnectors={selectedConnectors}
								searchMode={searchMode}
								onSearchModeChange={onSearchModeChange}

							/>
						</div>
					</div>
					<ChatPanelContainer />
				</div>
			</LlamaIndexChatSection>
		</chatInterfaceContext.Provider>
	);
}
