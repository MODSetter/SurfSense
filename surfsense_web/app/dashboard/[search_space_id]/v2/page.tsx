"use client";

import { useChat } from "@ai-sdk/react";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import ChatMain from "@/components/chat_v2/ChatMain";

export default function ResearcherPageV2() {
    const { search_space_id, chat_id } = useParams();
    const router = useRouter();

    const [token, setToken] = useState<string | null>(null);

    useEffect(() => {
        setToken(localStorage.getItem("surfsense_bearer_token"));
    }, []);

    const handleQuerySubmit = (input: string, handleSubmit: () => void) => {
        const createChat = async () => {
            try {
                if (!token) {
                    console.error("Authentication token not found");
                    return;
                }

                // Create a new chat
                const response = await fetch(
                    `${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/chats/`,
                    {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json",
                            Authorization: `Bearer ${token}`,
                        },
                        body: JSON.stringify({
                            type: "QNA",
                            title: "Untitled Chat", // Empty title initially
                            initial_connectors: [], // No default connectors
                            messages: [
                                {
                                    role: "user",
                                    content: input,
                                },
                            ],
                            search_space_id: Number(search_space_id),
                        }),
                    }
                );

                if (!response.ok) {
                    throw new Error(
                        `Failed to create chat: ${response.statusText}`
                    );
                }

                const data = await response.json();

                router.replace(`/dashboard/${search_space_id}/v2/${data.id}`);
            } catch (err) {
                console.error("Error creating chat:", err);
            }
        };

        if (!chat_id) {
            createChat();
            return;
        }
    };

    const handler = useChat({
        api: `${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/chat`,
        streamProtocol: "data",
        headers: {
            ...(token && { Authorization: `Bearer ${token}` }),
        },
        body: {
            data: {
                search_space_id: search_space_id,
                selected_connectors: [],
                research_mode: "QNA",
                search_mode: "DOCUMENTS",
                document_ids_to_add_in_context: [],
            },
        },
        onError: (error) => {
            console.error("Chat error:", error);
            // You can add additional error handling here if needed
        },
    });

    return <ChatMain handler={handler} handleQuerySubmit={handleQuerySubmit} />;
}
