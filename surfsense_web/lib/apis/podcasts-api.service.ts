import z from "zod";
import { logger } from "@/lib/logger";
import {
	type DeletePodcastRequest,
	deletePodcastRequest,
	deletePodcastResponse,
	type GeneratePodcastRequest,
	type GetPodcastByChatIdRequest,
	type GetPodcastsRequest,
	generatePodcastRequest,
	getPodcastByChaIdResponse,
	getPodcastByChatIdRequest,
	getPodcastsRequest,
	type LoadPodcastRequest,
	loadPodcastRequest,
	podcast,
} from "@/contracts/types/podcast.types";
import { ValidationError } from "../error";
import { baseApiService } from "./base-api.service";

class PodcastsApiService {
	getPodcasts = async (request: GetPodcastsRequest) => {
		// Validate the request
		const parsedRequest = getPodcastsRequest.safeParse(request);

		if (!parsedRequest.success) {
			logger.error("Invalid request:", parsedRequest.error);

			// Format a user friendly error message
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

		return baseApiService.get(`/api/v1/podcasts?${queryParams}`, z.array(podcast));
	};

	getPodcastByChatId = async (request: GetPodcastByChatIdRequest) => {
		// Validate the request
		const parsedRequest = getPodcastByChatIdRequest.safeParse(request);

		if (!parsedRequest.success) {
			logger.error("Invalid request:", parsedRequest.error);

			// Format a user friendly error message
			const errorMessage = parsedRequest.error.errors.map((err) => err.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.get(
			`/api/v1/podcasts/by-chat/${request.chat_id}`,
			getPodcastByChaIdResponse
		);
	};

	generatePodcast = async (request: GeneratePodcastRequest) => {
		// Validate the request
		const parsedRequest = generatePodcastRequest.safeParse(request);

		if (!parsedRequest.success) {
			logger.error("Invalid request:", parsedRequest.error);

			// Format a user friendly error message
			const errorMessage = parsedRequest.error.errors.map((err) => err.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.post(`/api/v1/podcasts/generate`, undefined, {
			body: parsedRequest.data,
		});
	};

	loadPodcast = async ({
		request,
		controller,
	}: {
		request: LoadPodcastRequest;
		controller?: AbortController;
	}) => {
		// Validate the request
		const parsedRequest = loadPodcastRequest.safeParse(request);

		if (!parsedRequest.success) {
			logger.error("Invalid request:", parsedRequest.error);

			// Format a user friendly error message
			const errorMessage = parsedRequest.error.errors.map((err) => err.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return await baseApiService.getBlob(`/api/v1/podcasts/${request.id}/stream`, {
			signal: controller?.signal,
		});
	};

	deletePodcast = async (request: DeletePodcastRequest) => {
		// Validate the request
		const parsedRequest = deletePodcastRequest.safeParse(request);

		if (!parsedRequest.success) {
			logger.error("Invalid request:", parsedRequest.error);

			// Format a user friendly error message
			const errorMessage = parsedRequest.error.errors.map((err) => err.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.delete(`/api/v1/podcasts/${request.id}`, deletePodcastResponse);
	};
}

export const podcastsApiService = new PodcastsApiService();
