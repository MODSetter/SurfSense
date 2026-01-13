import {
	type CreateSearchSpaceRequest,
	createSearchSpaceRequest,
	createSearchSpaceResponse,
	type DeleteSearchSpaceRequest,
	deleteSearchSpaceRequest,
	deleteSearchSpaceResponse,
	type GetSearchSpaceRequest,
	type GetSearchSpacesRequest,
	getSearchSpaceRequest,
	getSearchSpaceResponse,
	getSearchSpacesRequest,
	getSearchSpacesResponse,
	leaveSearchSpaceResponse,
	type UpdateSearchSpaceRequest,
	updateSearchSpaceRequest,
	updateSearchSpaceResponse,
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

			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
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

			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.post(`/api/v1/searchspaces`, createSearchSpaceResponse, {
			body: parsedRequest.data,
		});
	};

	/**
	 * Get a single search space by ID
	 */
	getSearchSpace = async (request: GetSearchSpaceRequest) => {
		const parsedRequest = getSearchSpaceRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.get(`/api/v1/searchspaces/${request.id}`, getSearchSpaceResponse);
	};

	/**
	 * Update an existing search space
	 */
	updateSearchSpace = async (request: UpdateSearchSpaceRequest) => {
		const parsedRequest = updateSearchSpaceRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.put(`/api/v1/searchspaces/${request.id}`, updateSearchSpaceResponse, {
			body: parsedRequest.data.data,
		});
	};

	/**
	 * Delete a search space
	 */
	deleteSearchSpace = async (request: DeleteSearchSpaceRequest) => {
		const parsedRequest = deleteSearchSpaceRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.delete(`/api/v1/searchspaces/${request.id}`, deleteSearchSpaceResponse);
	};

	/**
	 * Leave a search space (remove own membership)
	 * This is used by non-owners to leave a shared search space
	 */
	leaveSearchSpace = async (searchSpaceId: number) => {
		return baseApiService.delete(
			`/api/v1/searchspaces/${searchSpaceId}/members/me`,
			leaveSearchSpaceResponse
		);
	};
}

export const searchSpacesApiService = new SearchSpacesApiService();
