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
    getAnnotationData,
} from "@llamaindex/chat-ui";
import { Document } from "@/hooks/use-documents";
import { CustomChatInput } from "@/components/chat_v2/ChatInputGroup";
import { ResearchMode } from "@/components/chat";
import TerminalDisplay from "@/components/chat_v2/ChatTerminal";
import ChatSourcesDisplay from "@/components/chat_v2/ChatSources";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { ExternalLink } from "lucide-react";

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

const CitationDisplay: React.FC<{index: number, node: any}> = ({index, node}) => {


    const truncateText = (text: string, maxLength: number = 200) => {
        if (text.length <= maxLength) return text;
        return text.substring(0, maxLength) + '...';
    };

    const handleUrlClick = (e: React.MouseEvent, url: string) => {
        e.preventDefault();
        e.stopPropagation();
        window.open(url, '_blank', 'noopener,noreferrer');
    };

    return (
        <Popover >
            <PopoverTrigger asChild >
                <span className="text-[10px] font-bold bg-slate-500 hover:bg-slate-600 text-white rounded-full w-4 h-4 inline-flex items-center justify-center align-super cursor-pointer transition-colors">
                    {index + 1}
                </span>
            </PopoverTrigger>
            <PopoverContent className="w-80 p-4 space-y-3 relative" align="start" >
                {/* External Link Button - Top Right */}
                {node?.url && (
                    <button
                        onClick={(e) => handleUrlClick(e, node.url)}
                        className="absolute top-3 right-3 inline-flex items-center justify-center w-6 h-6 text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-200 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded transition-colors"
                        title="Open in new tab"
                    >
                        <ExternalLink size={14} />
                    </button>
                )}
                
                {/* Heading */}
                <div className="text-sm font-semibold text-slate-900 dark:text-slate-100 pr-8">
                    {node?.metadata?.group_name || 'Source'}
                </div>
                
                {/* Source */}
                <div className="text-xs text-slate-600 dark:text-slate-400 font-medium">
                    {node?.metadata?.title || 'Untitled'}
                </div>
                
                {/* Body */}
                <div className="text-xs text-slate-700 dark:text-slate-300 leading-relaxed">
                    {truncateText(node?.text || 'No content available')}
                </div>
            </PopoverContent>
        </Popover>
    );
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
                        <ChatMessage.Content.Markdown citationComponent={CitationDisplay} />
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
