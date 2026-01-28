import {
	type ClonePublicChatRequest,
	type ClonePublicChatResponse,
	type CompleteCloneRequest,
	type CompleteCloneResponse,
	clonePublicChatRequest,
	clonePublicChatResponse,
	completeCloneRequest,
	completeCloneResponse,
	type GetPublicChatRequest,
	type GetPublicChatResponse,
	getPublicChatRequest,
	getPublicChatResponse,
} from "@/contracts/types/public-chat.types";
import { ValidationError } from "../error";
import { baseApiService } from "./base-api.service";

class PublicChatApiService {
	/**
	 * Get a public chat by share token.
	 * No authentication required.
	 */
	getPublicChat = async (request: GetPublicChatRequest): Promise<GetPublicChatResponse> => {
		const parsed = getPublicChatRequest.safeParse(request);

		if (!parsed.success) {
			const errorMessage = parsed.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.get(`/api/v1/public/${parsed.data.share_token}`, getPublicChatResponse);
	};

	/**
	 * Clone a public chat to the user's account.
	 * Creates an empty thread and returns thread_id for redirect.
	 * Requires authentication.
	 */
	clonePublicChat = async (request: ClonePublicChatRequest): Promise<ClonePublicChatResponse> => {
		const parsed = clonePublicChatRequest.safeParse(request);

		if (!parsed.success) {
			const errorMessage = parsed.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.post(
			`/api/v1/public/${parsed.data.share_token}/clone`,
			clonePublicChatResponse
		);
	};

	/**
	 * Complete the clone by copying messages and podcasts.
	 * Called from the chat page after redirect.
	 * Requires authentication.
	 */
	completeClone = async (request: CompleteCloneRequest): Promise<CompleteCloneResponse> => {
		const parsed = completeCloneRequest.safeParse(request);

		if (!parsed.success) {
			const errorMessage = parsed.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.post(
			`/api/v1/threads/${parsed.data.thread_id}/complete-clone`,
			completeCloneResponse
		);
	};
}

export const publicChatApiService = new PublicChatApiService();
