"use client";

import { useChat, Message, CreateMessage } from "@ai-sdk/react";
import { useParams, useRouter } from "next/navigation";
import { useEffect } from "react";
import ChatMain from "@/components/chat_v2/ChatMain";
import { ResearchMode } from "@/components/chat";
import { useChatState, useChatAPI } from "@/hooks/useChat";

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

    // Single useChat handler for both cases
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
                document_ids_to_add_in_context: [],
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
        router.replace(`/dashboard/${search_space_id}/v2/${newChatId}`);
        return newChatId;
    };

    useEffect(() => {
        if (token && !isNewChat && chatIdParam) {
            setIsLoading(true);
            loadChatData(chatIdParam);
        }
    }, [token, isNewChat, chatIdParam]);

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
        <ChatMain
            handler={{
                ...handler,
                append: isNewChat ? customHandlerAppend : handler.append,
            }}
        />
    );
}
