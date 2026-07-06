import {
	imageGenerationDetail,
	imageGenerationList,
} from "@/contracts/types/image-generations.types";
import { baseApiService } from "./base-api.service";

const BASE = "/api/v1/image-generations";

class ImageGenerationsApiService {
	list = async (searchSpaceId: number, limit = 100) => {
		const qs = new URLSearchParams({
			workspace_id: String(searchSpaceId),
			limit: String(limit),
		}).toString();
		return baseApiService.get(`${BASE}?${qs}`, imageGenerationList);
	};

	getDetail = async (imageGenId: number) => {
		return baseApiService.get(`${BASE}/${imageGenId}`, imageGenerationDetail);
	};
}

export const imageGenerationsApiService = new ImageGenerationsApiService();
