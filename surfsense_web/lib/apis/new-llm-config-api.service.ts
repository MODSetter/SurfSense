import {
	type CreateNewLLMConfigRequest,
	createNewLLMConfigRequest,
	createNewLLMConfigResponse,
	type DeleteNewLLMConfigRequest,
	deleteNewLLMConfigRequest,
	deleteNewLLMConfigResponse,
	type GetNewLLMConfigRequest,
	type GetNewLLMConfigsRequest,
	getDefaultSystemInstructionsResponse,
	getGlobalNewLLMConfigsResponse,
	getLLMPreferencesResponse,
	getNewLLMConfigRequest,
	getNewLLMConfigResponse,
	getNewLLMConfigsRequest,
	getNewLLMConfigsResponse,
	type UpdateLLMPreferencesRequest,
	type UpdateNewLLMConfigRequest,
	updateLLMPreferencesRequest,
	updateLLMPreferencesResponse,
	updateNewLLMConfigRequest,
	updateNewLLMConfigResponse,
} from "@/contracts/types/new-llm-config.types";
import { ValidationError } from "../error";
import { baseApiService } from "./base-api.service";

class NewLLMConfigApiService {
	/**
	 * Get all global NewLLMConfigs available to all users
	 */
	getGlobalConfigs = async () => {
		return baseApiService.get(`/api/v1/global-new-llm-configs`, getGlobalNewLLMConfigsResponse);
	};

	/**
	 * Get default system instructions template
	 */
	getDefaultSystemInstructions = async () => {
		return baseApiService.get(
			`/api/v1/new-llm-configs/default-system-instructions`,
			getDefaultSystemInstructionsResponse
		);
	};

	/**
	 * Create a new NewLLMConfig for a search space
	 */
	createConfig = async (request: CreateNewLLMConfigRequest) => {
		const parsedRequest = createNewLLMConfigRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);
			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.post(`/api/v1/new-llm-configs`, createNewLLMConfigResponse, {
			body: parsedRequest.data,
		});
	};

	/**
	 * Get a list of NewLLMConfigs for a search space
	 */
	getConfigs = async (request: GetNewLLMConfigsRequest) => {
		const parsedRequest = getNewLLMConfigsRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);
			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		const queryParams = new URLSearchParams({
			search_space_id: String(parsedRequest.data.search_space_id),
			...(parsedRequest.data.skip !== undefined && { skip: String(parsedRequest.data.skip) }),
			...(parsedRequest.data.limit !== undefined && { limit: String(parsedRequest.data.limit) }),
		}).toString();

		return baseApiService.get(`/api/v1/new-llm-configs?${queryParams}`, getNewLLMConfigsResponse);
	};

	/**
	 * Get a single NewLLMConfig by ID
	 */
	getConfig = async (request: GetNewLLMConfigRequest) => {
		const parsedRequest = getNewLLMConfigRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);
			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.get(
			`/api/v1/new-llm-configs/${parsedRequest.data.id}`,
			getNewLLMConfigResponse
		);
	};

	/**
	 * Update an existing NewLLMConfig
	 */
	updateConfig = async (request: UpdateNewLLMConfigRequest) => {
		const parsedRequest = updateNewLLMConfigRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);
			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		const { id, data } = parsedRequest.data;

		return baseApiService.put(`/api/v1/new-llm-configs/${id}`, updateNewLLMConfigResponse, {
			body: data,
		});
	};

	/**
	 * Delete a NewLLMConfig
	 */
	deleteConfig = async (request: DeleteNewLLMConfigRequest) => {
		const parsedRequest = deleteNewLLMConfigRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);
			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.delete(
			`/api/v1/new-llm-configs/${parsedRequest.data.id}`,
			deleteNewLLMConfigResponse
		);
	};

	/**
	 * Get LLM preferences for a search space
	 */
	getLLMPreferences = async (searchSpaceId: number) => {
		return baseApiService.get(
			`/api/v1/search-spaces/${searchSpaceId}/llm-preferences`,
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
			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		const { search_space_id, data } = parsedRequest.data;

		return baseApiService.put(
			`/api/v1/search-spaces/${search_space_id}/llm-preferences`,
			updateLLMPreferencesResponse,
			{ body: data }
		);
	};
}

export const newLLMConfigApiService = new NewLLMConfigApiService();
