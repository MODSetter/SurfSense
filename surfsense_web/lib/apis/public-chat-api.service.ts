import {
	type ClonePublicChatRequest,
	type ClonePublicChatResponse,
	clonePublicChatRequest,
	clonePublicChatResponse,
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
}

export const publicChatApiService = new PublicChatApiService();
