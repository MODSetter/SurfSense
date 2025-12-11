import {
	type CreateSearchSpaceRequest,
	type GetSearchSpacesRequest,
	createSearchSpaceRequest,
	createSearchSpaceResponse,
	getSearchSpacesRequest,
	getSearchSpacesResponse,
} from "@/contracts/types/search-space.types";
import { ValidationError } from "../error";
import { baseApiService } from "./base-api.service";

class SearchSpacesApiService {
	/**
	 * Get a list of search spaces with optional filtering and pagination
	 */
	getSearchSpaces = async (request?: GetSearchSpacesRequest) => {
		const parsedRequest = getSearchSpacesRequest.safeParse(request || {});

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			const errorMessage = parsedRequest.error.errors.map((err) => err.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		// Transform query params to be string values
		const transformedQueryParams = parsedRequest.data.queryParams
			? Object.fromEntries(
					Object.entries(parsedRequest.data.queryParams).map(([k, v]) => {
						return [k, String(v)];
					})
				)
			: undefined;

		const queryParams = transformedQueryParams
			? new URLSearchParams(transformedQueryParams).toString()
			: "";

		return baseApiService.get(`/api/v1/searchspaces?${queryParams}`, getSearchSpacesResponse);
	};

	/**
	 * Create a new search space
	 */
	createSearchSpace = async (request: CreateSearchSpaceRequest) => {
		const parsedRequest = createSearchSpaceRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			const errorMessage = parsedRequest.error.errors.map((err) => err.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.post(`/api/v1/searchspaces`, createSearchSpaceResponse, {
			body: parsedRequest.data,
		});
	};
}

export const searchSpacesApiService = new SearchSpacesApiService();
