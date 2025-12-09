import {
	type CreateLLMConfigRequest,
	createLLMConfigRequest,
	createLLMConfigResponse,
	type DeleteLLMConfigRequest,
	deleteLLMConfigRequest,
	deleteLLMConfigResponse,
	type GetGlobalLLMConfigsResponse,
	type GetLLMConfigRequest,
	type GetLLMConfigsRequest,
	type GetLLMPreferencesRequest,
	getGlobalLLMConfigsResponse,
	getLLMConfigRequest,
	getLLMConfigResponse,
	getLLMConfigsRequest,
	getLLMConfigsResponse,
	getLLMPreferencesRequest,
	getLLMPreferencesResponse,
	type UpdateLLMConfigRequest,
	type UpdateLLMPreferencesRequest,
	updateLLMConfigRequest,
	updateLLMConfigResponse,
	updateLLMPreferencesRequest,
	updateLLMPreferencesResponse,
} from "@/contracts/types/llm-config.types";
import { ValidationError } from "../error";
import { baseApiService } from "./base-api.service";

class LLMConfigApiService {
	/**
	 * Get all global LLM configurations available to all users
	 */
	getGlobalLLMConfigs = async () => {
		return baseApiService.get(`/api/v1/global-llm-configs`, getGlobalLLMConfigsResponse);
	};

	/**
	 * Create a new LLM configuration for a search space
	 */
	createLLMConfig = async (request: CreateLLMConfigRequest) => {
		const parsedRequest = createLLMConfigRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			const errorMessage = parsedRequest.error.errors.map((err) => err.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.post(`/api/v1/llm-configs`, createLLMConfigResponse, {
			body: parsedRequest.data,
		});
	};

	/**
	 * Get a list of LLM configurations for a search space
	 */
	getLLMConfigs = async (request: GetLLMConfigsRequest) => {
		const parsedRequest = getLLMConfigsRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			const errorMessage = parsedRequest.error.errors.map((err) => err.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		// Transform query params to be string values
		const transformedQueryParams = parsedRequest.data.queryParams
			? Object.fromEntries(
					Object.entries(parsedRequest.data.queryParams).map(([k, v]) => {
						return [k, String(v)];
					})
				)
			: undefined;

		const queryParams = transformedQueryParams
			? new URLSearchParams(transformedQueryParams).toString()
			: "";

		return baseApiService.get(`/api/v1/llm-configs?${queryParams}`, getLLMConfigsResponse);
	};

	/**
	 * Get a single LLM configuration by ID
	 */
	getLLMConfig = async (request: GetLLMConfigRequest) => {
		const parsedRequest = getLLMConfigRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			const errorMessage = parsedRequest.error.errors.map((err) => err.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.get(`/api/v1/llm-configs/${request.id}`, getLLMConfigResponse);
	};

	/**
	 * Update an existing LLM configuration
	 */
	updateLLMConfig = async (request: UpdateLLMConfigRequest) => {
		const parsedRequest = updateLLMConfigRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			const errorMessage = parsedRequest.error.errors.map((err) => err.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		const { id, data } = parsedRequest.data;

		return baseApiService.put(`/api/v1/llm-configs/${id}`, updateLLMConfigResponse, {
			body: data,
		});
	};

	/**
	 * Delete an LLM configuration
	 */
	deleteLLMConfig = async (request: DeleteLLMConfigRequest) => {
		const parsedRequest = deleteLLMConfigRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			const errorMessage = parsedRequest.error.errors.map((err) => err.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.delete(`/api/v1/llm-configs/${request.id}`, deleteLLMConfigResponse);
	};

	/**
	 * Get LLM preferences for a search space
	 */
	getLLMPreferences = async (request: GetLLMPreferencesRequest) => {
		const parsedRequest = getLLMPreferencesRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			const errorMessage = parsedRequest.error.errors.map((err) => err.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.get(
			`/api/v1/search-spaces/${request.search_space_id}/llm-preferences`,
			getLLMPreferencesResponse
		);
	};

	/**
	 * Update LLM preferences for a search space
	 */
	updateLLMPreferences = async (request: UpdateLLMPreferencesRequest) => {
		const parsedRequest = updateLLMPreferencesRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			const errorMessage = parsedRequest.error.errors.map((err) => err.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		const { search_space_id, data } = parsedRequest.data;

		return baseApiService.put(
			`/api/v1/search-spaces/${search_space_id}/llm-preferences`,
			updateLLMPreferencesResponse,
			{
				body: data,
			}
		);
	};
}

export const llmConfigApiService = new LLMConfigApiService();
