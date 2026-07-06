import { reportList } from "@/contracts/types/reports.types";
import { baseApiService } from "./base-api.service";

const BASE = "/api/v1/reports";

class ReportsApiService {
	list = async (searchSpaceId: number, limit = 200) => {
		const qs = new URLSearchParams({
			workspace_id: String(searchSpaceId),
			limit: String(limit),
		}).toString();
		return baseApiService.get(`${BASE}?${qs}`, reportList);
	};
}

export const reportsApiService = new ReportsApiService();
