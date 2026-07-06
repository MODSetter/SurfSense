import { z } from "zod";
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
	type UpdateSearchSpaceApiAccessRequest,
	type UpdateSearchSpaceRequest,
	updateSearchSpaceApiAccessRequest,
	updateSearchSpaceApiAccessResponse,
	updateSearchSpaceRequest,
	updateSearchSpaceResponse,
} from "@/contracts/types/workspace.types";
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

		return baseApiService.get(`/api/v1/workspaces?${queryParams}`, getSearchSpacesResponse);
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

		return baseApiService.post(`/api/v1/workspaces`, createSearchSpaceResponse, {
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

		return baseApiService.get(`/api/v1/workspaces/${request.id}`, getSearchSpaceResponse);
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

		return baseApiService.put(`/api/v1/workspaces/${request.id}`, updateSearchSpaceResponse, {
			body: parsedRequest.data.data,
		});
	};

	updateSearchSpaceApiAccess = async (request: UpdateSearchSpaceApiAccessRequest) => {
		const parsedRequest = updateSearchSpaceApiAccessRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);
			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.put(
			`/api/v1/workspaces/${request.id}/api-access`,
			updateSearchSpaceApiAccessResponse,
			{
				body: { api_access_enabled: parsedRequest.data.api_access_enabled },
			}
		);
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

		return baseApiService.delete(`/api/v1/workspaces/${request.id}`, deleteSearchSpaceResponse);
	};

	/**
	 * Trigger AI file sorting for all documents in a search space
	 */
	triggerAiSort = async (searchSpaceId: number) => {
		return baseApiService.post(
			`/api/v1/workspaces/${searchSpaceId}/ai-sort`,
			z.object({ message: z.string() }),
			{}
		);
	};

	/**
	 * Leave a search space (remove own membership)
	 * This is used by non-owners to leave a shared search space
	 */
	leaveSearchSpace = async (searchSpaceId: number) => {
		return baseApiService.delete(
			`/api/v1/workspaces/${searchSpaceId}/members/me`,
			leaveSearchSpaceResponse
		);
	};
}

export const searchSpacesApiService = new SearchSpacesApiService();
