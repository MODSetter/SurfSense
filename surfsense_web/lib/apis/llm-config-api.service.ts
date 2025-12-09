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
}

export const llmConfigApiService = new LLMConfigApiService();
