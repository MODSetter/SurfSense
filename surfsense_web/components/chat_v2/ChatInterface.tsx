"use client";

import {
    ChatSection,
    ChatHandler,
    ChatCanvas,
    ChatMessages,
    useChatUI,
    ChatMessage,
} from "@llamaindex/chat-ui";
import { Document } from "@/hooks/use-documents";
import { CustomChatInput } from "@/components/chat_v2/ChatInputGroup";
import { ResearchMode } from "@/components/chat";
import React from "react";
import TerminalDisplay from "@/components/chat_v2/ChatTerminal";

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

function ChatMessageDisplay() {
    const { messages } = useChatUI();

    return (
        <ChatMessages className="flex-1">
            <ChatMessages.List className="p-4">
                {messages.map((message, index) => (
                    <div key={`Message-${index}`}>
                        {message.role === "assistant" && (
                            <TerminalDisplay messages={messages} />
                        )}
                        <ChatMessage
                            key={index}
                            message={message}
                            isLast={index === messages.length - 1}
                        />
                    </div>
                ))}
            </ChatMessages.List>
            <ChatMessages.Loading />
        </ChatMessages>
    );
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
        <ChatSection handler={handler} className="flex h-full">
            <div className="flex flex-1 flex-col">
                <ChatMessageDisplay />
                <div className="border-t p-4">
                    <CustomChatInput
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

            <ChatCanvas className="w-1/2 border-l" />
        </ChatSection>
    );
}
