import { videoPresentationList } from "@/contracts/types/video-presentations.types";
import { baseApiService } from "./base-api.service";

const BASE = "/api/v1/video-presentations";

class VideoPresentationsApiService {
	list = async (searchSpaceId: number, limit = 200) => {
		const qs = new URLSearchParams({
			workspace_id: String(searchSpaceId),
			limit: String(limit),
		}).toString();
		return baseApiService.get(`${BASE}?${qs}`, videoPresentationList);
	};
}

export const videoPresentationsApiService = new VideoPresentationsApiService();
