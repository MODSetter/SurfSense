"use client";

import {
    ChatSection,
    ChatHandler,
    ChatCanvas,
    ChatMessages,
} from "@llamaindex/chat-ui";
import { Document } from "@/hooks/use-documents";
import { CustomChatInput } from "@/components/chat_v2/ChatInputGroup";
import { ResearchMode } from "@/components/chat";
import React from "react";

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
        <ChatSection handler={handler} className="flex h-full">
            <div className="flex flex-1 flex-col">
                <ChatMessages className="flex-1">
                    <ChatMessages.List className="p-4">
                        {/* Custom message rendering */}
                    </ChatMessages.List>
                    <ChatMessages.Loading />
                </ChatMessages>

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
