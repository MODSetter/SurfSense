"use client";

import { type ChatHandler, ChatSection as LlamaIndexChatSection } from "@llamaindex/chat-ui";
import { useParams } from "next/navigation";
import { ChatInputUI } from "@/components/chat/ChatInputGroup";
import { ChatMessagesUI } from "@/components/chat/ChatMessages";
import type { Document } from "@/contracts/types/document.types";

interface ChatInterfaceProps {
	handler: ChatHandler;
	onDocumentSelectionChange?: (documents: Document[]) => void;
	selectedDocuments?: Document[];
	onConnectorSelectionChange?: (connectorTypes: string[]) => void;
	selectedConnectors?: string[];
	topK?: number;
	onTopKChange?: (topK: number) => void;
}

export default function ChatInterface({
	handler,
	onDocumentSelectionChange,
	selectedDocuments = [],
	onConnectorSelectionChange,
	selectedConnectors = [],
	topK = 10,
	onTopKChange,
}: ChatInterfaceProps) {
	const { chat_id, search_space_id } = useParams();

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
						topK={topK}
						onTopKChange={onTopKChange}
					/>
				</div>
			</div>
		</LlamaIndexChatSection>
	);
}
