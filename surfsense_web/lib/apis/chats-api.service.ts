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
	type GetChatsBySearchSpaceRequest,
	getChatDetailsRequest,
	getChatsBySearchSpaceRequest,
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

	getChatsBySearchSpace = async (request: GetChatsBySearchSpaceRequest) => {
		// Validate the request
		const parsedRequest = getChatsBySearchSpaceRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			// Format a user frendly error message
			const errorMessage = parsedRequest.error.errors.map((err) => err.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		const queryParams = parsedRequest.data.queryParams
			? new URLSearchParams(parsedRequest.data.queryParams).toString()
			: undefined;

		return baseApiService.get(`/api/v1/chats?${queryParams}`, z.array(chatSummary));
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

		const { type, title, initial_connectors, messages, search_space_id } = parsedRequest.data;

		return baseApiService.post(
			`/api/v1/chats`,

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
