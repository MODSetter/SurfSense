"use client";

import { useChat, Message, CreateMessage } from "@ai-sdk/react";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo } from "react";
import ChatInterface from "@/components/chat_v2/ChatInterface";
import { ResearchMode } from "@/components/chat";
import { useChatState, useChatAPI } from "@/hooks/useChat";
import { Document } from "@/hooks/use-documents";

export default function ResearchChatPageV2() {
    const { search_space_id, chat_id } = useParams();
    const router = useRouter();

    const chatIdParam = Array.isArray(chat_id) ? chat_id[0] : chat_id;
    const isNewChat = !chatIdParam;

    const {
        token,
        isLoading,
        setIsLoading,
        searchMode,
        researchMode,
        setResearchMode,
        selectedConnectors,
        setSelectedConnectors,
        selectedDocuments,
        setSelectedDocuments,
    } = useChatState({
        search_space_id: search_space_id as string,
        chat_id: chatIdParam,
    });

    const { fetchChatDetails, updateChat, createChat } = useChatAPI({
        token,
        search_space_id: search_space_id as string,
        researchMode,
        selectedConnectors,
    });

    // Memoize document IDs to prevent infinite re-renders
    const documentIds = useMemo(() => {
        return selectedDocuments.map((doc) => doc.id);
    }, [selectedDocuments]);

    // Helper functions for localStorage management
    const getStorageKey = (searchSpaceId: string, chatId: string) =>
        `surfsense_selected_docs_${searchSpaceId}_${chatId}`;

    const storeSelectedDocuments = (
        searchSpaceId: string,
        chatId: string,
        documents: Document[]
    ) => {
        const key = getStorageKey(searchSpaceId, chatId);
        localStorage.setItem(key, JSON.stringify(documents));
    };

    const restoreSelectedDocuments = (
        searchSpaceId: string,
        chatId: string
    ): Document[] | null => {
        const key = getStorageKey(searchSpaceId, chatId);
        const stored = localStorage.getItem(key);
        if (stored) {
            localStorage.removeItem(key); // Clean up after restoration
            try {
                return JSON.parse(stored);
            } catch (error) {
                console.error("Error parsing stored documents:", error);
                return null;
            }
        }
        return null;
    };

    const handler = useChat({
        api: `${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/chat`,
        streamProtocol: "data",
        initialMessages: [],
        headers: {
            ...(token && { Authorization: `Bearer ${token}` }),
        },
        body: {
            data: {
                search_space_id: search_space_id,
                selected_connectors: selectedConnectors,
                research_mode: researchMode,
                search_mode: searchMode,
                document_ids_to_add_in_context: documentIds,
            },
        },
        onError: (error) => {
            console.error("Chat error:", error);
        },
    });

    const customHandlerAppend = async (
        message: Message | CreateMessage,
        chatRequestOptions?: { data?: any }
    ) => {
        const newChatId = await createChat(message.content);
        if (newChatId) {
            // Store selected documents before navigation
            storeSelectedDocuments(
                search_space_id as string,
                newChatId,
                selectedDocuments
            );
            router.replace(`/dashboard/${search_space_id}/v2/${newChatId}`);
        }
        return newChatId;
    };

    useEffect(() => {
        if (token && !isNewChat && chatIdParam) {
            setIsLoading(true);
            loadChatData(chatIdParam);
        }
    }, [token, isNewChat, chatIdParam]);

    // Restore selected documents from localStorage on page load
    useEffect(() => {
        if (chatIdParam && search_space_id) {
            const restoredDocuments = restoreSelectedDocuments(
                search_space_id as string,
                chatIdParam
            );
            if (restoredDocuments && restoredDocuments.length > 0) {
                setSelectedDocuments(restoredDocuments);
            }
        }
    }, [chatIdParam, search_space_id, setSelectedDocuments]);

    const loadChatData = async (chatId: string) => {
        try {
            const chatData = await fetchChatDetails(chatId);
            if (!chatData) return;

            // Update configuration from chat data
            if (chatData.type) {
                setResearchMode(chatData.type as ResearchMode);
            }

            if (
                chatData.initial_connectors &&
                Array.isArray(chatData.initial_connectors)
            ) {
                setSelectedConnectors(chatData.initial_connectors);
            }

            // Load existing messages
            if (chatData.messages && Array.isArray(chatData.messages)) {
                if (
                    chatData.messages.length === 1 &&
                    chatData.messages[0].role === "user"
                ) {
                    // Single user message - append to trigger LLM response
                    handler.append({
                        role: "user",
                        content: chatData.messages[0].content,
                    });
                } else if (chatData.messages.length > 1) {
                    // Multiple messages - set them all
                    handler.setMessages(chatData.messages);
                }
            }
        } finally {
            setIsLoading(false);
        }
    };

    // Auto-update chat when messages change (only for existing chats)
    useEffect(() => {
        if (
            !isNewChat &&
            chatIdParam &&
            handler.status === "ready" &&
            handler.messages.length > 0 &&
            handler.messages[handler.messages.length - 1]?.role === "assistant"
        ) {
            updateChat(chatIdParam, handler.messages);
        }
    }, [handler.messages, handler.status, chatIdParam, isNewChat, updateChat]);

    if (isLoading) {
        return (
            <div className="flex items-center justify-center h-full">
                <div>Loading...</div>
            </div>
        );
    }

    return (
        <ChatInterface
            handler={{
                ...handler,
                append: isNewChat ? customHandlerAppend : handler.append,
            }}
            onDocumentSelectionChange={setSelectedDocuments}
            selectedDocuments={selectedDocuments}
        />
    );
}
