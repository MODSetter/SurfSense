import type { Message } from "@ai-sdk/react";
import { useCallback, useEffect, useState } from "react";
import type { ResearchMode } from "@/components/chat";
import type { Document } from "@/hooks/use-documents";

interface UseChatStateProps {
	search_space_id: string;
	chat_id?: string;
}

export function useChatState({ chat_id }: UseChatStateProps) {
	const [token, setToken] = useState<string | null>(null);
	const [isLoading, setIsLoading] = useState(false);
	const [currentChatId, setCurrentChatId] = useState<string | null>(chat_id || null);

	// Chat configuration state
	const [searchMode, setSearchMode] = useState<"DOCUMENTS" | "CHUNKS">("DOCUMENTS");
	const [researchMode, setResearchMode] = useState<ResearchMode>("QNA");
	const [selectedConnectors, setSelectedConnectors] = useState<string[]>([]);
	const [selectedDocuments, setSelectedDocuments] = useState<Document[]>([]);
	const [topK, setTopK] = useState<number>(5);

	useEffect(() => {
		const bearerToken = localStorage.getItem("surfsense_bearer_token");
		setToken(bearerToken);
	}, []);

	return {
		token,
		setToken,
		isLoading,
		setIsLoading,
		currentChatId,
		setCurrentChatId,
		searchMode,
		setSearchMode,
		researchMode,
		setResearchMode,
		selectedConnectors,
		setSelectedConnectors,
		selectedDocuments,
		setSelectedDocuments,
		topK,
		setTopK,
	};
}

interface UseChatAPIProps {
	token: string | null;
	search_space_id: string;
}

export function useChatAPI({ token, search_space_id }: UseChatAPIProps) {
	const fetchChatDetails = useCallback(
		async (chatId: string) => {
			if (!token) return null;

			try {
				const response = await fetch(
					`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/chats/${Number(chatId)}`,
					{
						method: "GET",
						headers: {
							"Content-Type": "application/json",
							Authorization: `Bearer ${token}`,
						},
					}
				);

				if (!response.ok) {
					throw new Error(`Failed to fetch chat details: ${response.statusText}`);
				}

				return await response.json();
			} catch (err) {
				console.error("Error fetching chat details:", err);
				return null;
			}
		},
		[token]
	);

	const createChat = useCallback(
		async (
			initialMessage: string,
			researchMode: ResearchMode,
			selectedConnectors: string[]
		): Promise<string | null> => {
			if (!token) {
				console.error("Authentication token not found");
				return null;
			}

			try {
				const response = await fetch(
					`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/chats`,
					{
						method: "POST",
						headers: {
							"Content-Type": "application/json",
							Authorization: `Bearer ${token}`,
						},
						body: JSON.stringify({
							type: researchMode,
							title: "Untitled Chat",
							initial_connectors: selectedConnectors,
							messages: [
								{
									role: "user",
									content: initialMessage,
								},
							],
							search_space_id: Number(search_space_id),
						}),
					}
				);

				if (!response.ok) {
					throw new Error(`Failed to create chat: ${response.statusText}`);
				}

				const data = await response.json();
				return data.id;
			} catch (err) {
				console.error("Error creating chat:", err);
				return null;
			}
		},
		[token, search_space_id]
	);

	const updateChat = useCallback(
		async (
			chatId: string,
			messages: Message[],
			researchMode: ResearchMode,
			selectedConnectors: string[]
		) => {
			if (!token) return;

			try {
				const userMessages = messages.filter((msg) => msg.role === "user");
				if (userMessages.length === 0) return;

				const title = userMessages[0].content;

				const response = await fetch(
					`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/chats/${Number(chatId)}`,
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
					throw new Error(`Failed to update chat: ${response.statusText}`);
				}
			} catch (err) {
				console.error("Error updating chat:", err);
			}
		},
		[token, search_space_id]
	);

	return {
		fetchChatDetails,
		createChat,
		updateChat,
	};
}
