import {
	type CreateVisionLLMConfigRequest,
	createVisionLLMConfigRequest,
	createVisionLLMConfigResponse,
	deleteVisionLLMConfigResponse,
	getGlobalVisionLLMConfigsResponse,
	getModelListResponse,
	getVisionLLMConfigsResponse,
	type UpdateVisionLLMConfigRequest,
	updateVisionLLMConfigRequest,
	updateVisionLLMConfigResponse,
} from "@/contracts/types/new-llm-config.types";
import { ValidationError } from "../error";
import { baseApiService } from "./base-api.service";

class VisionLLMConfigApiService {
	getModels = async () => {
		return baseApiService.get(`/api/v1/vision-models`, getModelListResponse);
	};

	getGlobalConfigs = async () => {
		return baseApiService.get(
			`/api/v1/global-vision-llm-configs`,
			getGlobalVisionLLMConfigsResponse
		);
	};

	createConfig = async (request: CreateVisionLLMConfigRequest) => {
		const parsed = createVisionLLMConfigRequest.safeParse(request);
		if (!parsed.success) {
			const msg = parsed.error.issues.map((i) => i.message).join(", ");
			throw new ValidationError(`Invalid request: ${msg}`);
		}
		return baseApiService.post(`/api/v1/vision-llm-configs`, createVisionLLMConfigResponse, {
			body: parsed.data,
		});
	};

	getConfigs = async (searchSpaceId: number) => {
		const params = new URLSearchParams({
			search_space_id: String(searchSpaceId),
		}).toString();
		return baseApiService.get(`/api/v1/vision-llm-configs?${params}`, getVisionLLMConfigsResponse);
	};

	updateConfig = async (request: UpdateVisionLLMConfigRequest) => {
		const parsed = updateVisionLLMConfigRequest.safeParse(request);
		if (!parsed.success) {
			const msg = parsed.error.issues.map((i) => i.message).join(", ");
			throw new ValidationError(`Invalid request: ${msg}`);
		}
		const { id, data } = parsed.data;
		return baseApiService.put(`/api/v1/vision-llm-configs/${id}`, updateVisionLLMConfigResponse, {
			body: data,
		});
	};

	deleteConfig = async (id: number) => {
		return baseApiService.delete(`/api/v1/vision-llm-configs/${id}`, deleteVisionLLMConfigResponse);
	};
}

export const visionLLMConfigApiService = new VisionLLMConfigApiService();
