import { z } from "zod";
import {
	type CreateWorkspaceRequest,
	createWorkspaceRequest,
	createWorkspaceResponse,
	type DeleteWorkspaceRequest,
	deleteWorkspaceRequest,
	deleteWorkspaceResponse,
	type GetWorkspaceRequest,
	type GetWorkspacesRequest,
	getWorkspaceRequest,
	getWorkspaceResponse,
	getWorkspacesRequest,
	getWorkspacesResponse,
	leaveWorkspaceResponse,
	type UpdateWorkspaceApiAccessRequest,
	type UpdateWorkspaceRequest,
	updateWorkspaceApiAccessRequest,
	updateWorkspaceApiAccessResponse,
	updateWorkspaceRequest,
	updateWorkspaceResponse,
} from "@/contracts/types/workspace.types";
import { ValidationError } from "../error";
import { baseApiService } from "./base-api.service";

class WorkspacesApiService {
	/**
	 * Get a list of workspaces with optional filtering and pagination
	 */
	getWorkspaces = async (request?: GetWorkspacesRequest) => {
		const parsedRequest = getWorkspacesRequest.safeParse(request || {});

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

		return baseApiService.get(`/api/v1/workspaces?${queryParams}`, getWorkspacesResponse);
	};

	/**
	 * Create a new workspace
	 */
	createWorkspace = async (request: CreateWorkspaceRequest) => {
		const parsedRequest = createWorkspaceRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.post(`/api/v1/workspaces`, createWorkspaceResponse, {
			body: parsedRequest.data,
		});
	};

	/**
	 * Get a single workspace by ID
	 */
	getWorkspace = async (request: GetWorkspaceRequest) => {
		const parsedRequest = getWorkspaceRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.get(`/api/v1/workspaces/${request.id}`, getWorkspaceResponse);
	};

	/**
	 * Update an existing workspace
	 */
	updateWorkspace = async (request: UpdateWorkspaceRequest) => {
		const parsedRequest = updateWorkspaceRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.put(`/api/v1/workspaces/${request.id}`, updateWorkspaceResponse, {
			body: parsedRequest.data.data,
		});
	};

	updateWorkspaceApiAccess = async (request: UpdateWorkspaceApiAccessRequest) => {
		const parsedRequest = updateWorkspaceApiAccessRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);
			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.put(
			`/api/v1/workspaces/${request.id}/api-access`,
			updateWorkspaceApiAccessResponse,
			{
				body: { api_access_enabled: parsedRequest.data.api_access_enabled },
			}
		);
	};

	/**
	 * Delete a workspace
	 */
	deleteWorkspace = async (request: DeleteWorkspaceRequest) => {
		const parsedRequest = deleteWorkspaceRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.delete(`/api/v1/workspaces/${request.id}`, deleteWorkspaceResponse);
	};

	/**
	 * Trigger AI file sorting for all documents in a workspace
	 */
	triggerAiSort = async (workspaceId: number) => {
		return baseApiService.post(
			`/api/v1/workspaces/${workspaceId}/ai-sort`,
			z.object({ message: z.string() }),
			{}
		);
	};

	/**
	 * Leave a workspace (remove own membership)
	 * This is used by non-owners to leave a shared workspace
	 */
	leaveWorkspace = async (workspaceId: number) => {
		return baseApiService.delete(
			`/api/v1/workspaces/${workspaceId}/members/me`,
			leaveWorkspaceResponse
		);
	};
}

export const workspacesApiService = new WorkspacesApiService();
