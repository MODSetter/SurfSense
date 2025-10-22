"use client";

import { type ChatHandler, ChatSection as LlamaIndexChatSection } from "@llamaindex/chat-ui";
import { PanelRight } from "lucide-react";
import { useParams } from "next/navigation";
import { createContext, useState } from "react";
import type { ResearchMode } from "@/components/chat";
import { ChatInputUI } from "@/components/chat/ChatInputGroup";
import { ChatMessagesUI } from "@/components/chat/ChatMessages";
import type { Document } from "@/hooks/use-documents";
import { cn } from "@/lib/utils";
import { ChatPanelContainer } from "./ChatPannel/ChatPannelContainer";

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
	const [isChatPannelOpen, setIsChatPannelOpen] = useState(false);
	const contextValue = {
		isChatPannelOpen,
		setIsChatPannelOpen,
	};

	const { chat_id: chatId } = useParams();

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
					{chatId ? (
						<div
							className={cn(
								"border rounded-2xl shrink-0 bg-sidebar flex flex-col h-full transition-all",
								isChatPannelOpen ? "w-72" : "w-14"
							)}
						>
							<div
								className={cn(
									"w-full border-b p-2 flex items-center transition-all ",
									isChatPannelOpen ? "justify-end" : " justify-center "
								)}
							>
								<button
									type="button"
									onClick={() => setIsChatPannelOpen(!isChatPannelOpen)}
									className={cn(" shrink-0 rounded-full p-2 w-fit hover:bg-muted")}
								>
									<PanelRight className="h-5 w-5" strokeWidth={1.5} />
								</button>
							</div>

							<div className="border-b rounded-lg grow-1">
								<ChatPanelContainer chatId={typeof chatId === "string" ? chatId : chatId[0]} />
							</div>
						</div>
					) : null}
				</div>
			</LlamaIndexChatSection>
		</chatInterfaceContext.Provider>
	);
}
