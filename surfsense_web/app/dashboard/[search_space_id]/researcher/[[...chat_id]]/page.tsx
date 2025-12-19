"use client";

import { type CreateMessage, type Message, useChat } from "@ai-sdk/react";
import { useAtom, useAtomValue } from "jotai";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useRef } from "react";
import { createChatMutationAtom, updateChatMutationAtom } from "@/atoms/chats/chat-mutation.atoms";
import { activeChatAtom } from "@/atoms/chats/chat-query.atoms";
import { activeChatIdAtom } from "@/atoms/chats/ui.atoms";
import { documentTypeCountsAtom } from "@/atoms/documents/document-query.atoms";
import ChatInterface from "@/components/chat/ChatInterface";
import type { Document } from "@/contracts/types/document.types";
import { useChatState } from "@/hooks/use-chat";
import { useSearchSourceConnectors } from "@/hooks/use-search-source-connectors";

export default function ResearcherPage() {
	const { search_space_id } = useParams();
	const router = useRouter();
	const hasSetInitialConnectors = useRef(false);
	const hasInitiatedResponse = useRef<string | null>(null);
	const activeChatId = useAtomValue(activeChatIdAtom);
	const { data: activeChatState, isFetching: isChatLoading } = useAtomValue(activeChatAtom);
	const { mutateAsync: createChat } = useAtomValue(createChatMutationAtom);
	const { mutateAsync: updateChat } = useAtomValue(updateChatMutationAtom);
	const isNewChat = !activeChatId;

	// Reset the flag when chat ID changes (but not hasInitiatedResponse - we need to remember if we already initiated)
	useEffect(() => {
		hasSetInitialConnectors.current = false;
	}, [activeChatId]);

	const {
		token,
		researchMode,
		selectedConnectors,
		setSelectedConnectors,
		selectedDocuments,
		setSelectedDocuments,
		topK,
		setTopK,
	} = useChatState({
		search_space_id: search_space_id as string,
		chat_id: activeChatId ?? undefined,
	});

	// Fetch all available sources (document types + live search connectors)
	// Use the documentTypeCountsAtom for fetching document types
	const [documentTypeCountsQuery] = useAtom(documentTypeCountsAtom);
	const { data: documentTypeCountsData } = documentTypeCountsQuery;

	// Transform the response into the expected format
	const documentTypes = useMemo(() => {
		if (!documentTypeCountsData) return [];
		return Object.entries(documentTypeCountsData).map(([type, count]) => ({
			type,
			count,
		}));
	}, [documentTypeCountsData]);

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
		// Use the first message content as the chat title (truncated to 100 chars)
		const messageContent = typeof message.content === 'string' ? message.content : '';
		const chatTitle = messageContent.slice(0, 100) || "Untitled Chat";
		
		const newChat = await createChat({
			type: researchMode,
			title: chatTitle,
			initial_connectors: selectedConnectors,
			messages: [
				{
					role: "user",
					content: message.content,
				},
			],
			search_space_id: Number(search_space_id),
		});
		if (newChat) {
			// Store chat state before navigation
			storeChatState(search_space_id as string, String(newChat.id), {
				selectedDocuments,
				selectedConnectors,
				researchMode,
				topK,
			});
			router.replace(`/dashboard/${search_space_id}/researcher/${newChat.id}`);
		}
		return String(newChat.id);
	};

	useEffect(() => {
		if (token && !isNewChat && activeChatId) {
			const chatData = activeChatState?.chatDetails;
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
					// Only if we haven't already initiated for this chat and handler doesn't have messages yet
					if (hasInitiatedResponse.current !== activeChatId && handler.messages.length === 0) {
						hasInitiatedResponse.current = activeChatId;
						handler.append({
							role: "user",
							content: chatData.messages[0].content,
						});
					}
				} else if (chatData.messages.length > 1) {
					// Multiple messages - set them all
					handler.setMessages(chatData.messages);
				}
			}
		}
	}, [token, isNewChat, activeChatId, isChatLoading]);

	// Restore chat state from localStorage on page load
	useEffect(() => {
		if (activeChatId && search_space_id) {
			const restoredState = restoreChatState(search_space_id as string, activeChatId);
			if (restoredState) {
				setSelectedDocuments(restoredState.selectedDocuments);
				setSelectedConnectors(restoredState.selectedConnectors);
				setTopK(restoredState.topK);
				// researchMode is always "QNA", no need to restore
			}
		}
	}, [
		activeChatId,
		isChatLoading,
		search_space_id,
		setSelectedDocuments,
		setSelectedConnectors,
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

	// Auto-update chat when messages change (only for existing chats)
	useEffect(() => {
		if (
			!isNewChat &&
			activeChatId &&
			handler.status === "ready" &&
			handler.messages.length > 0 &&
			handler.messages[handler.messages.length - 1]?.role === "assistant"
		) {
			const userMessages = handler.messages.filter((msg) => msg.role === "user");
			if (userMessages.length === 0) return;
			const title = userMessages[0].content;

			updateChat({
				type: researchMode,
				title: title,
				initial_connectors: selectedConnectors,
				messages: handler.messages,
				search_space_id: Number(search_space_id),
				id: Number(activeChatId),
			});
		}
	}, [handler.messages, handler.status, activeChatId, isNewChat, isChatLoading]);

	if (isChatLoading) {
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
			topK={topK}
			onTopKChange={setTopK}
		/>
	);
}
