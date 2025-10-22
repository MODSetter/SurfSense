"use client";

import { type ChatHandler, ChatSection as LlamaIndexChatSection } from "@llamaindex/chat-ui";
import { PanelRight } from "lucide-react";
import { useParams } from "next/navigation";
import { createContext, useState } from "react";
import type { ResearchMode } from "@/components/chat";
import { ChatInputUI } from "@/components/chat/ChatInputGroup";
import { ChatMessagesUI } from "@/components/chat/ChatMessages";
import type { Document } from "@/hooks/use-documents";
import { ChatPanelContainer } from "./ChatPannel/ChatPanelContainer";

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
	const { chat_id } = useParams();
	const [isChatPannelOpen, setIsChatPannelOpen] = useState(false);
	const contextValue = {
		isChatPannelOpen,
		setIsChatPannelOpen,
		chat_id: typeof chat_id === "string" ? chat_id : chat_id ? chat_id[0] : "",
	};

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
