"use client";

import React from "react";
import {
	ChatSection as LlamaIndexChatSection,
	ChatHandler,
} from "@llamaindex/chat-ui";
import { Document } from "@/hooks/use-documents";
import { ChatInputUI } from "@/components/chat/ChatInputGroup";
import { ResearchMode } from "@/components/chat";
import { ChatMessagesUI } from "@/components/chat/ChatMessages";

interface ChatInterfaceProps {
	handler: ChatHandler;
	onDocumentSelectionChange?: (documents: Document[]) => void;
	selectedDocuments?: Document[];
	onConnectorSelectionChange?: (connectorTypes: string[]) => void;
	selectedConnectors?: string[];
	searchMode?: "DOCUMENTS" | "CHUNKS";
	onSearchModeChange?: (mode: "DOCUMENTS" | "CHUNKS") => void;
	researchMode?: ResearchMode;
	onResearchModeChange?: (mode: ResearchMode) => void;
}

export default function ChatInterface({
	handler,
	onDocumentSelectionChange,
	selectedDocuments = [],
	onConnectorSelectionChange,
	selectedConnectors = [],
	searchMode,
	onSearchModeChange,
	researchMode,
	onResearchModeChange,
}: ChatInterfaceProps) {
	return (
		<LlamaIndexChatSection handler={handler} className="flex h-full">
			<div className="flex flex-1 flex-col">
				<ChatMessagesUI />
				<div className="border-t p-4">
					<ChatInputUI
						onDocumentSelectionChange={onDocumentSelectionChange}
						selectedDocuments={selectedDocuments}
						onConnectorSelectionChange={onConnectorSelectionChange}
						selectedConnectors={selectedConnectors}
						searchMode={searchMode}
						onSearchModeChange={onSearchModeChange}
						researchMode={researchMode}
						onResearchModeChange={onResearchModeChange}
					/>
				</div>
			</div>
		</LlamaIndexChatSection>
	);
}
