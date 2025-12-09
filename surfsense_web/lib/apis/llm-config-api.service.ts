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
}

export const llmConfigApiService = new LLMConfigApiService();
