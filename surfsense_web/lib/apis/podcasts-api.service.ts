import {
	type GeneratePodcastRequest,
	type GetPodcastByChatIdRequest,
	generatePodcastRequest,
	getPodcastByChatIdRequest,
	type Podcast,
	podcast,
} from "@/contracts/types/podcast.types";
import { ValidationError } from "../error";
import { baseApiService } from "./base-api.service";

class PodcastsApiService {
	getPodcastByChatId = async (request: GetPodcastByChatIdRequest) => {
		// Validate the request
		const parsedRequest = getPodcastByChatIdRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			// Format a user frendly error message
			const errorMessage = parsedRequest.error.errors.map((err) => err.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.get(`/api/v1/podcasts/by-chat/${request.chat_id}`, podcast);
	};

	generatePodcast = async (request: GeneratePodcastRequest) => {
		// Validate the request
		const parsedRequest = generatePodcastRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			// Format a user frendly error message
			const errorMessage = parsedRequest.error.errors.map((err) => err.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.post(`/api/v1/podcasts/generate`, undefined, {
			body: request,
		});
	};

	loadPodcast = async ({
		podcast,
		controller,
	}: {
		podcast: Podcast;
		controller?: AbortController;
	}) => {
		return await baseApiService.getBlob(`/api/v1/podcasts/${podcast.id}/stream`, {
			signal: controller?.signal,
		});
	};
}

export const podcastsApiService = new PodcastsApiService();
