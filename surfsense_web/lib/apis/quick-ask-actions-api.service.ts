import {
	type QuickAskActionCreateRequest,
	type QuickAskActionUpdateRequest,
	quickAskActionCreateRequest,
	quickAskActionDeleteResponse,
	quickAskActionRead,
	quickAskActionUpdateRequest,
	quickAskActionsListResponse,
} from "@/contracts/types/quick-ask-actions.types";
import { ValidationError } from "@/lib/error";
import { baseApiService } from "./base-api.service";

class QuickAskActionsApiService {
	list = async (searchSpaceId?: number) => {
		const params = new URLSearchParams();
		if (searchSpaceId !== undefined) {
			params.set("search_space_id", String(searchSpaceId));
		}
		const queryString = params.toString();
		const url = queryString
			? `/api/v1/quick-ask-actions?${queryString}`
			: "/api/v1/quick-ask-actions";

		return baseApiService.get(url, quickAskActionsListResponse);
	};

	create = async (request: QuickAskActionCreateRequest) => {
		const parsed = quickAskActionCreateRequest.safeParse(request);
		if (!parsed.success) {
			const errorMessage = parsed.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.post("/api/v1/quick-ask-actions", quickAskActionRead, {
			body: parsed.data,
		});
	};

	update = async (actionId: number, request: QuickAskActionUpdateRequest) => {
		const parsed = quickAskActionUpdateRequest.safeParse(request);
		if (!parsed.success) {
			const errorMessage = parsed.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.put(`/api/v1/quick-ask-actions/${actionId}`, quickAskActionRead, {
			body: parsed.data,
		});
	};

	delete = async (actionId: number) => {
		return baseApiService.delete(
			`/api/v1/quick-ask-actions/${actionId}`,
			quickAskActionDeleteResponse
		);
	};
}

export const quickAskActionsApiService = new QuickAskActionsApiService();
