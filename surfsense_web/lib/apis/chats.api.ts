import type { Chat, ChatDetails } from "@/app/dashboard/[search_space_id]/chats/chats-client";
import { ResearchMode } from "@/components/chat/types";
import { Message } from "@ai-sdk/react";

export const fetchChatDetails = async (
	chatId: string,
	authToken: string
): Promise<ChatDetails | null> => {
	const response = await fetch(
		`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/chats/${Number(chatId)}`,
		{
			method: "GET",
			headers: {
				"Content-Type": "application/json",
				Authorization: `Bearer ${authToken}`,
			},
		}
	);

	if (!response.ok) {
		throw new Error(`Failed to fetch chat details: ${response.statusText}`);
	}

	return await response.json();
};

export const fetchChatsBySearchSpace = async (
	searchSpaceId: string,
	authToken: string
): Promise<ChatDetails[] | null> => {
	const response = await fetch(
		`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/chats?search_space_id=${searchSpaceId}`,
		{
			method: "GET",
			headers: {
				"Content-Type": "application/json",
				Authorization: `Bearer ${authToken}`,
			},
		}
	);
	if (!response.ok) {
		throw new Error(`Failed to fetch chats: ${response.statusText}`);
	}

	return await response.json();
};

export const deleteChat = async (chatId: number, authToken: string) => {
	const response = await fetch(
		`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/chats/${chatId}`,
		{
			method: "DELETE",
			headers: {
				Authorization: `Bearer ${authToken}`,
			},
		}
	);

	if (!response.ok) {
		throw new Error(`Failed to delete chat: ${response.statusText}`);
	}

	return await response.json();
};

export const createChat = async (
	initialMessage: string,
	researchMode: ResearchMode,
	selectedConnectors: string[],
	authToken: string,
	searchSpaceId: number
): Promise<Chat | null> => {
	const response = await fetch(`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/chats`, {
		method: "POST",
		headers: {
			"Content-Type": "application/json",
			Authorization: `Bearer ${authToken}`,
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
			search_space_id: searchSpaceId,
		}),
	});

	if (!response.ok) {
		throw new Error(`Failed to create chat: ${response.statusText}`);
	}

	return await response.json();
};

export const updateChat = async (
	chatId: string,
	messages: Message[],
	researchMode: ResearchMode,
	selectedConnectors: string[],
	authToken: string,
	searchSpaceId: number
) => {
	const userMessages = messages.filter((msg) => msg.role === "user");
	if (userMessages.length === 0) return;

	const title = userMessages[0].content;

	const response = await fetch(
		`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/chats/${Number(chatId)}`,
		{
			method: "PUT",
			headers: {
				"Content-Type": "application/json",
				Authorization: `Bearer ${authToken}`,
			},
			body: JSON.stringify({
				type: researchMode,
				title: title,
				initial_connectors: selectedConnectors,
				messages: messages,
				search_space_id: searchSpaceId,
			}),
		}
	);

	if (!response.ok) {
		throw new Error(`Failed to update chat: ${response.statusText}`);
	}
};

export const fetchChats = async (
	searchSpaceId: string,
	limit: number,
	skip: number,
	authToken: string
) => {
	const response = await fetch(
		`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/chats?limit=${limit}&skip=${skip}&search_space_id=${searchSpaceId}`,
		{
			headers: {
				Authorization: `Bearer ${authToken}`,
			},
			method: "GET",
		}
	);

	if (!response.ok) {
		throw new Error(`Failed to fetch chats: ${response.status}`);
	}

	return await response.json();
};
