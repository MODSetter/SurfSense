"use client";

import { type CreateMessage, type Message, useChat } from "@ai-sdk/react";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useRef } from "react";
import ChatInterface from "@/components/chat/ChatInterface";
import { useChatAPI, useChatState } from "@/hooks/use-chat";
import { useDocumentTypes } from "@/hooks/use-document-types";
import type { Document } from "@/hooks/use-documents";
import { useSearchSourceConnectors } from "@/hooks/use-search-source-connectors";

export default function ResearcherPage() {
	const { search_space_id, chat_id } = useParams();
	const router = useRouter();
	const hasSetInitialConnectors = useRef(false);

	const chatIdParam = Array.isArray(chat_id) ? chat_id[0] : chat_id;
	const isNewChat = !chatIdParam;

	// Reset the flag when chat ID changes
	useEffect(() => {
		hasSetInitialConnectors.current = false;
	}, [chatIdParam]);

	const {
		token,
		isLoading,
		setIsLoading,
		searchMode,
		setSearchMode,
		researchMode,
		selectedConnectors,
		setSelectedConnectors,
		selectedDocuments,
		setSelectedDocuments,
		topK,
		setTopK,
	} = useChatState({
		search_space_id: search_space_id as string,
		chat_id: chatIdParam,
	});

	const { fetchChatDetails, updateChat, createChat } = useChatAPI({
		token,
		search_space_id: search_space_id as string,
	});

	// Fetch all available sources (document types + live search connectors)
	const { documentTypes } = useDocumentTypes(Number(search_space_id));
	const { connectors: searchConnectors } = useSearchSourceConnectors(
		false,
		Number(search_space_id)
	);

	// Filter for non-indexable connectors (live search)
	const liveSearchConnectors = useMemo(
		() => searchConnectors.filter((connector) => !connector.is_indexable),
		[searchConnectors]
	);

	// Memoize document IDs to prevent infinite re-renders
	const documentIds = useMemo(() => {
		return selectedDocuments.map((doc) => doc.id);
	}, [selectedDocuments]);

	// Memoize connector types to prevent infinite re-renders
	const connectorTypes = useMemo(() => {
		return selectedConnectors;
	}, [selectedConnectors]);

	// Unified localStorage management for chat state
	interface ChatState {
		selectedDocuments: Document[];
		selectedConnectors: string[];
		searchMode: "DOCUMENTS" | "CHUNKS";
		researchMode: "QNA"; // Always QNA mode
		topK: number;
	}

	const getChatStateStorageKey = (searchSpaceId: string, chatId: string) =>
		`surfsense_chat_state_${searchSpaceId}_${chatId}`;

	const storeChatState = (searchSpaceId: string, chatId: string, state: ChatState) => {
		const key = getChatStateStorageKey(searchSpaceId, chatId);
		localStorage.setItem(key, JSON.stringify(state));
	};

	const restoreChatState = (searchSpaceId: string, chatId: string): ChatState | null => {
		const key = getChatStateStorageKey(searchSpaceId, chatId);
		const stored = localStorage.getItem(key);
		if (stored) {
			localStorage.removeItem(key); // Clean up after restoration
			try {
				return JSON.parse(stored);
			} catch (error) {
				console.error("Error parsing stored chat state:", error);
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
				selected_connectors: connectorTypes,
				research_mode: researchMode,
				search_mode: searchMode,
				document_ids_to_add_in_context: documentIds,
				top_k: topK,
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
		const newChatId = await createChat(message.content, researchMode, selectedConnectors);
		if (newChatId) {
			// Store chat state before navigation
			storeChatState(search_space_id as string, newChatId, {
				selectedDocuments,
				selectedConnectors,
				searchMode,
				researchMode,
				topK,
			});
			router.replace(`/dashboard/${search_space_id}/researcher/${newChatId}`);
		}
		return newChatId;
	};

	useEffect(() => {
		if (token && !isNewChat && chatIdParam) {
			setIsLoading(true);
			loadChatData(chatIdParam);
		}
	}, [token, isNewChat, chatIdParam]);

	// Restore chat state from localStorage on page load
	useEffect(() => {
		if (chatIdParam && search_space_id) {
			const restoredState = restoreChatState(search_space_id as string, chatIdParam);
			if (restoredState) {
				setSelectedDocuments(restoredState.selectedDocuments);
				setSelectedConnectors(restoredState.selectedConnectors);
				setSearchMode(restoredState.searchMode);
				setTopK(restoredState.topK);
				// researchMode is always "QNA", no need to restore
			}
		}
	}, [
		chatIdParam,
		search_space_id,
		setSelectedDocuments,
		setSelectedConnectors,
		setSearchMode,
		setTopK,
	]);

	// Set all sources as default for new chats (only once on initial mount)
	useEffect(() => {
		if (
			isNewChat &&
			!hasSetInitialConnectors.current &&
			selectedConnectors.length === 0 &&
			documentTypes.length > 0
		) {
			// Combine all document types and live search connectors
			const allSourceTypes = [
				...documentTypes.map((dt) => dt.type),
				...liveSearchConnectors.map((c) => c.connector_type),
			];

			if (allSourceTypes.length > 0) {
				setSelectedConnectors(allSourceTypes);
				hasSetInitialConnectors.current = true;
			}
		}
	}, [
		isNewChat,
		documentTypes,
		liveSearchConnectors,
		selectedConnectors.length,
		setSelectedConnectors,
	]);

	const loadChatData = async (chatId: string) => {
		try {
			const chatData = await fetchChatDetails(chatId);
			if (!chatData) return;

			// Update configuration from chat data
			// researchMode is always "QNA", no need to set from chat data

			if (chatData.initial_connectors && Array.isArray(chatData.initial_connectors)) {
				setSelectedConnectors(chatData.initial_connectors);
			}

			// Load existing messages
			if (chatData.messages && Array.isArray(chatData.messages)) {
				if (chatData.messages.length === 1 && chatData.messages[0].role === "user") {
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
			updateChat(chatIdParam, handler.messages, researchMode, selectedConnectors);
		}
	}, [handler.messages, handler.status, chatIdParam, isNewChat]);

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
			onConnectorSelectionChange={setSelectedConnectors}
			selectedConnectors={selectedConnectors}
			searchMode={searchMode}
			onSearchModeChange={setSearchMode}
			topK={topK}
			onTopKChange={setTopK}
		/>
	);
}
