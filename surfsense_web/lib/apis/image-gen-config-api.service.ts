import {
	type CreateImageGenConfigRequest,
	createImageGenConfigRequest,
	createImageGenConfigResponse,
	type UpdateImageGenConfigRequest,
	updateImageGenConfigRequest,
	updateImageGenConfigResponse,
	deleteImageGenConfigResponse,
	getImageGenConfigsResponse,
	getGlobalImageGenConfigsResponse,
} from "@/contracts/types/new-llm-config.types";
import { ValidationError } from "../error";
import { baseApiService } from "./base-api.service";

class ImageGenConfigApiService {
	/**
	 * Get all global image generation configs (from YAML, negative IDs)
	 */
	getGlobalConfigs = async () => {
		return baseApiService.get(
			`/api/v1/global-image-generation-configs`,
			getGlobalImageGenConfigsResponse
		);
	};

	/**
	 * Create a new image generation config for a search space
	 */
	createConfig = async (request: CreateImageGenConfigRequest) => {
		const parsed = createImageGenConfigRequest.safeParse(request);
		if (!parsed.success) {
			const msg = parsed.error.issues.map((i) => i.message).join(", ");
			throw new ValidationError(`Invalid request: ${msg}`);
		}
		return baseApiService.post(
			`/api/v1/image-generation-configs`,
			createImageGenConfigResponse,
			{ body: parsed.data }
		);
	};

	/**
	 * Get image generation configs for a search space
	 */
	getConfigs = async (searchSpaceId: number) => {
		const params = new URLSearchParams({
			search_space_id: String(searchSpaceId),
		}).toString();
		return baseApiService.get(
			`/api/v1/image-generation-configs?${params}`,
			getImageGenConfigsResponse
		);
	};

	/**
	 * Update an existing image generation config
	 */
	updateConfig = async (request: UpdateImageGenConfigRequest) => {
		const parsed = updateImageGenConfigRequest.safeParse(request);
		if (!parsed.success) {
			const msg = parsed.error.issues.map((i) => i.message).join(", ");
			throw new ValidationError(`Invalid request: ${msg}`);
		}
		const { id, data } = parsed.data;
		return baseApiService.put(
			`/api/v1/image-generation-configs/${id}`,
			updateImageGenConfigResponse,
			{ body: data }
		);
	};

	/**
	 * Delete an image generation config
	 */
	deleteConfig = async (id: number) => {
		return baseApiService.delete(
			`/api/v1/image-generation-configs/${id}`,
			deleteImageGenConfigResponse
		);
	};
}

export const imageGenConfigApiService = new ImageGenConfigApiService();
