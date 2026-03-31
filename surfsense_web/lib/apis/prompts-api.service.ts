import {
	type PromptCreateRequest,
	type PromptUpdateRequest,
	promptCreateRequest,
	promptDeleteResponse,
	promptRead,
	promptsListResponse,
	promptUpdateRequest,
} from "@/contracts/types/prompts.types";
import { ValidationError } from "@/lib/error";
import { baseApiService } from "./base-api.service";

class PromptsApiService {
	list = async (searchSpaceId?: number) => {
		const params = new URLSearchParams();
		if (searchSpaceId !== undefined) {
			params.set("search_space_id", String(searchSpaceId));
		}
		const queryString = params.toString();
		const url = queryString ? `/api/v1/prompts?${queryString}` : "/api/v1/prompts";

		return baseApiService.get(url, promptsListResponse);
	};

	create = async (request: PromptCreateRequest) => {
		const parsed = promptCreateRequest.safeParse(request);
		if (!parsed.success) {
			const errorMessage = parsed.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.post("/api/v1/prompts", promptRead, {
			body: parsed.data,
		});
	};

	update = async (promptId: number, request: PromptUpdateRequest) => {
		const parsed = promptUpdateRequest.safeParse(request);
		if (!parsed.success) {
			const errorMessage = parsed.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.put(`/api/v1/prompts/${promptId}`, promptRead, {
			body: parsed.data,
		});
	};

	delete = async (promptId: number) => {
		return baseApiService.delete(`/api/v1/prompts/${promptId}`, promptDeleteResponse);
	};
}

export const promptsApiService = new PromptsApiService();
