import { z } from "zod";
import {
	type CreateChatRequest,
	chatDetails,
	chatSummary,
	createChatRequest,
	type DeleteChatRequest,
	deleteChatRequest,
	deleteChatResponse,
	type GetChatDetailsRequest,
	type GetChatsRequest,
	getChatDetailsRequest,
	getChatsRequest,
	type SearchChatsRequest,
	searchChatsRequest,
	type UpdateChatRequest,
	updateChatRequest,
} from "@/contracts/types/chat.types";
import { ValidationError } from "../error";
import { baseApiService } from "./base-api.service";

class ChatApiService {
	getChatDetails = async (request: GetChatDetailsRequest) => {
		// Validate the request
		const parsedRequest = getChatDetailsRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			// Format a user frendly error message
			const errorMessage = parsedRequest.error.errors.map((err) => err.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.get(`/api/v1/chats/${request.id}`, chatDetails);
	};

	getChats = async (request: GetChatsRequest) => {
		// Validate the request
		const parsedRequest = getChatsRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			// Format a user frendly error message
			const errorMessage = parsedRequest.error.errors.map((err) => err.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		// Transform queries params to be string values
		const transformedQueryParams = parsedRequest.data.queryParams
			? Object.fromEntries(
					Object.entries(parsedRequest.data.queryParams).map(([k, v]) => [k, String(v)])
				)
			: undefined;

		const queryParams = transformedQueryParams
			? new URLSearchParams(transformedQueryParams).toString()
			: undefined;

		return baseApiService.get(`/api/v1/chats?${queryParams}`, z.array(chatSummary));
	};

	searchChats = async (request: SearchChatsRequest) => {
		// Validate the request
		const parsedRequest = searchChatsRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			// Format a user frendly error message
			const errorMessage = parsedRequest.error.errors.map((err) => err.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		// Transform queries params to be string values
		const transformedQueryParams = Object.fromEntries(
			Object.entries(parsedRequest.data.queryParams).map(([k, v]) => [k, String(v)])
		);

		const queryParams = new URLSearchParams(transformedQueryParams).toString();

		return baseApiService.get(`/api/v1/chats/search?${queryParams}`, z.array(chatSummary));
	};

	deleteChat = async (request: DeleteChatRequest) => {
		// Validate the request
		const parsedRequest = deleteChatRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			// Format a user frendly error message
			const errorMessage = parsedRequest.error.errors.map((err) => err.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.delete(`/api/v1/chats/${request.id}`, deleteChatResponse);
	};

	createChat = async (request: CreateChatRequest) => {
		// Validate the request
		const parsedRequest = createChatRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			// Format a user frendly error message
			const errorMessage = parsedRequest.error.errors.map((err) => err.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.post(
			`/api/v1/chats`,

			chatSummary,
			{
				body: parsedRequest.data,
			}
		);
	};

	updateChat = async (request: UpdateChatRequest) => {
		// Validate the request
		const parsedRequest = updateChatRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			// Format a user frendly error message
			const errorMessage = parsedRequest.error.errors.map((err) => err.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		const { type, title, initial_connectors, messages, search_space_id, id } = parsedRequest.data;

		return baseApiService.put(
			`/api/v1/chats/${id}`,

			chatSummary,
			{
				body: {
					type,
					title,
					initial_connectors,
					messages,
					search_space_id,
				},
			}
		);
	};
}

export const chatsApiService = new ChatApiService();
