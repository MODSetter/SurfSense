import { ResearchMode } from "@/components/chat/types";
import { Message } from "@ai-sdk/react";
import {
	chatDetails,
	chatSummary,
	createChatRequest,
	CreateChatRequest,
	deleteChatRequest,
	DeleteChatRequest,
	getChatDetailsRequest,
	GetChatDetailsRequest,
	getChatsBySearchSpaceRequest,
	GetChatsBySearchSpaceRequest,
	deleteChatResponse,
	UpdateChatRequest,
	updateChatRequest,
} from "@/contracts/types/chat.types";
import { z } from "zod";
import { baseApiService } from "./base-api.service";

export class ChatApiService {
	fetchChatDetails = async (request: GetChatDetailsRequest) => {
		// Validate the request
		const parsedRequest = getChatDetailsRequest.safeParse(request);

		if (!parsedRequest.success) {
			throw new Error(`Invalid request: ${parsedRequest.error.message}`);
		}

		return baseApiService.get(`/api/v1/chats/${request.id}`, chatDetails);
	};

	fetchChatsBySearchSpace = async (request: GetChatsBySearchSpaceRequest) => {
		// Validate the request
		const parsedRequest = getChatsBySearchSpaceRequest.safeParse(request);

		if (!parsedRequest.success) {
			throw new Error(`Invalid request: ${parsedRequest.error.message}`);
		}

		return baseApiService.get(
			`/api/v1/chats?search_space_id=${request.search_space_id}`,
			z.array(chatSummary)
		);
	};

	deleteChat = async (request: DeleteChatRequest) => {
		// Validate the request
		const parsedRequest = deleteChatRequest.safeParse(request);

		if (!parsedRequest.success) {
			throw new Error(`Invalid request: ${parsedRequest.error.message}`);
		}

		return baseApiService.delete(`/api/v1/chats/${request.id}`, undefined, deleteChatResponse);
	};

	createChat = async (request: CreateChatRequest) => {
		// Validate the request
		const parsedRequest = createChatRequest.safeParse(request);

		if (!parsedRequest.success) {
			throw new Error(`Invalid request: ${parsedRequest.error.message}`);
		}

		const { type, title, initial_connectors, messages, search_space_id } = parsedRequest.data;

		return baseApiService.post(
			`/api/v1/chats`,
			{
				type,
				title,
				initial_connectors,
				messages,
				search_space_id,
			},
			chatSummary
		);
	};

	updateChat = async (request: UpdateChatRequest) => {
		// Validate the request
		const parsedRequest = updateChatRequest.safeParse(request);

		if (!parsedRequest.success) {
			throw new Error(`Invalid request: ${parsedRequest.error.message}`);
		}

		const { type, title, initial_connectors, messages, search_space_id, id } = parsedRequest.data;

		return baseApiService.put(
			`/api/v1/chats/${id}`,
			{
				type,
				title,
				initial_connectors,
				messages,
				search_space_id,
			},
			chatSummary
		);
	};
}
