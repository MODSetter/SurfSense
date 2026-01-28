import {
	type TogglePublicShareRequest,
	type TogglePublicShareResponse,
	togglePublicShareRequest,
	togglePublicShareResponse,
} from "@/contracts/types/chat-threads.types";
import { ValidationError } from "../error";
import { baseApiService } from "./base-api.service";

class ChatThreadsApiService {
	/**
	 * Toggle public sharing for a thread.
	 * Requires authentication.
	 */
	togglePublicShare = async (
		request: TogglePublicShareRequest
	): Promise<TogglePublicShareResponse> => {
		const parsed = togglePublicShareRequest.safeParse(request);

		if (!parsed.success) {
			const errorMessage = parsed.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.patch(
			`/api/v1/threads/${parsed.data.thread_id}/public-share`,
			togglePublicShareResponse,
			{ body: { enabled: parsed.data.enabled } }
		);
	};
}

export const chatThreadsApiService = new ChatThreadsApiService();
