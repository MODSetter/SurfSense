"use client";

import React from "react";
import {
    ChatSection,
    ChatHandler,
    ChatCanvas,
    ChatMessages,
    useChatUI,
    ChatMessage,
    Message,
} from "@llamaindex/chat-ui";
import { Document } from "@/hooks/use-documents";
import { CustomChatInput } from "@/components/chat_v2/ChatInputGroup";
import { ResearchMode } from "@/components/chat";
import TerminalDisplay from "@/components/chat_v2/ChatTerminal";
import ChatSourcesDisplay from "@/components/chat_v2/ChatSources";

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

function ChatMessageDisplay({
    message,
    isLast,
}: {
    message: Message;
    isLast: boolean;
}) {
    return (
        <ChatMessage
            message={message}
            isLast={isLast}
            className="flex flex-col "
        >
            {message.role === "assistant" ? (
                <div className="flex-1 flex flex-col space-y-4">
                    <TerminalDisplay message={message} />
                    <ChatSourcesDisplay message={message} />
                    <ChatMessage.Content className="flex-1">
                        <ChatMessage.Content.Markdown />
                    </ChatMessage.Content>
                    <ChatMessage.Actions className="flex-1 flex flex-row justify-end" />
                </div>
            ) : (
                <ChatMessage.Content className="flex-1">
                    <ChatMessage.Content.Markdown />
                </ChatMessage.Content>
            )}
        </ChatMessage>
    );
}

function ChatMessagesDisplay() {
    const { messages } = useChatUI();

    return (
        <ChatMessages className="flex-1">
            <ChatMessages.List className="p-4">
                {messages.map((message, index) => (
                    <ChatMessageDisplay
                        key={`Message-${index}`}
                        message={message}
                        isLast={index === messages.length - 1}
                    />
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
                <ChatMessagesDisplay />
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
