"use client";

import { Message, useChat } from "@ai-sdk/react";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import ChatMain from "@/components/chat_v2/ChatMain";
import { ResearchMode } from "@/components/chat";

export default function ResearcherChatPageV2() {
    const { search_space_id, chat_id } = useParams();

    const [token, setToken] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(false);

    // const [initialMessages, setInitialMessages] = useState<any[]>([]);

    const [searchMode, setSearchMode] = useState<"DOCUMENTS" | "CHUNKS">(
        "DOCUMENTS"
    );
    const [researchMode, setResearchMode] = useState<ResearchMode>("QNA");
    const [selectedConnectors, setSelectedConnectors] = useState<string[]>([]);

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
            // You can add additional error handling here if needed
        },
    });

    useEffect(() => {
        setIsLoading(true);
        let token = localStorage.getItem("surfsense_bearer_token");
        if (token) {
            setToken(token);
            fetchChatDetails(token);
            setIsLoading(false);
        }
    }, [chat_id]);

    const fetchChatDetails = async (token: string) => {
        try {
            if (!token) return;

            // console.log('Fetching chat details for chat ID:', chat_id);

            const response = await fetch(
                `${
                    process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL
                }/api/v1/chats/${Number(chat_id)}`,
                {
                    method: "GET",
                    headers: {
                        "Content-Type": "application/json",
                        Authorization: `Bearer ${token}`,
                    },
                }
            );

            if (!response.ok) {
                throw new Error(
                    `Failed to fetch chat details: ${response.statusText}`
                );
            }

            const chatData = await response.json();
            // console.log('Chat details fetched:', chatData);

            // Set research mode from chat data
            if (chatData.type) {
                setResearchMode(chatData.type as ResearchMode);
            }

            // Set connectors from chat data
            if (
                chatData.initial_connectors &&
                Array.isArray(chatData.initial_connectors)
            ) {
                setSelectedConnectors(chatData.initial_connectors);
            }

            if (chatData.messages && Array.isArray(chatData.messages)) {
                console.log("chatData.messages", chatData.messages);

                if (
                    chatData.messages.length === 1 &&
                    chatData.messages[0].role === "user"
                ) {
                    console.log("appending");
                    handler.append({
                        role: "user",
                        content: chatData.messages[0].content,
                    });
                } else {
                    console.log("setting");
                    handler.setMessages(chatData.messages);
                }
            }
        } catch (err) {
            console.error("Error fetching chat details:", err);
        }
    };

    const updateChat = async (messages: Message[]) => {
        try {
            const token = localStorage.getItem("surfsense_bearer_token");
            console.log("updating chat", messages, token);
            if (!token) return;

            // Find the first user message to use as title
            const userMessages = handler.messages.filter(
                (msg: any) => msg.role === "user"
            );

            console.log("userMessages", userMessages);
            console.log("handler.messages", handler.messages);

            if (userMessages.length === 0) return;

            // Use the first user message as the title
            const title = userMessages[0].content;

            // console.log('Updating chat with title:', title);

            // Update the chat
            console.log("messages", messages);
            const response = await fetch(
                `${
                    process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL
                }/api/v1/chats/${Number(chat_id)}`,
                {
                    method: "PUT",
                    headers: {
                        "Content-Type": "application/json",
                        Authorization: `Bearer ${token}`,
                    },
                    body: JSON.stringify({
                        type: researchMode,
                        title: title,
                        initial_connectors: selectedConnectors,
                        messages: messages,
                        search_space_id: Number(search_space_id),
                    }),
                }
            );

            if (!response.ok) {
                throw new Error(
                    `Failed to update chat: ${response.statusText}`
                );
            }

            // console.log('Chat updated successfully');
        } catch (err) {
            console.error("Error updating chat:", err);
        }
    };

    useEffect(() => {
        console.log("handler.messages", handler.messages, handler.status);
        if (
            handler.status === "ready" &&
            handler.messages.length > 0 &&
            handler.messages[handler.messages.length - 1]?.role === "assistant"
        ) {
            updateChat(handler.messages);
        }
    }, [handler.messages, handler.status]);

    const handleQuerySubmit = (input: string, handleSubmit: () => void) => {
        handleSubmit();
    };

    if (isLoading) {
        return <div>Loading...</div>;
    }

    return <ChatMain handler={handler} handleQuerySubmit={handleQuerySubmit} />;
}
