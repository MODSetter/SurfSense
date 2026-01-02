import {
	type CreateConnectorRequest,
	createConnectorRequest,
	createConnectorResponse,
	type DeleteConnectorRequest,
	deleteConnectorRequest,
	deleteConnectorResponse,
	type GetConnectorRequest,
	type GetConnectorsRequest,
	getConnectorRequest,
	getConnectorResponse,
	getConnectorsRequest,
	getConnectorsResponse,
	type IndexConnectorRequest,
	indexConnectorRequest,
	indexConnectorResponse,
	type ListGitHubRepositoriesRequest,
	type ListGoogleDriveFoldersRequest,
	listGitHubRepositoriesRequest,
	listGitHubRepositoriesResponse,
	listGoogleDriveFoldersRequest,
	listGoogleDriveFoldersResponse,
	type UpdateConnectorRequest,
	updateConnectorRequest,
	updateConnectorResponse,
} from "@/contracts/types/connector.types";
import { ValidationError } from "../error";
import { baseApiService } from "./base-api.service";

class ConnectorsApiService {
	/**
	 * Get all connectors for a search space
	 */
	getConnectors = async (request: GetConnectorsRequest) => {
		const parsedRequest = getConnectorsRequest.safeParse(request);

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

		return baseApiService.get(
			`/api/v1/search-source-connectors?${queryParams}`,
			getConnectorsResponse
		);
	};

	/**
	 * Get a single connector by ID
	 */
	getConnector = async (request: GetConnectorRequest) => {
		const parsedRequest = getConnectorRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.get(
			`/api/v1/search-source-connectors/${request.id}`,
			getConnectorResponse
		);
	};

	/**
	 * Create a new connector
	 */
	createConnector = async (request: CreateConnectorRequest) => {
		const parsedRequest = createConnectorRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		const { data, queryParams } = parsedRequest.data;

		// Transform query params to be string values
		const transformedQueryParams = Object.fromEntries(
			Object.entries(queryParams).map(([k, v]) => {
				return [k, String(v)];
			})
		);

		const queryString = new URLSearchParams(transformedQueryParams).toString();

		return baseApiService.post(
			`/api/v1/search-source-connectors?${queryString}`,
			createConnectorResponse,
			{
				body: data,
			}
		);
	};

	/**
	 * Update an existing connector
	 */
	updateConnector = async (request: UpdateConnectorRequest) => {
		const parsedRequest = updateConnectorRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		const { id, data } = parsedRequest.data;

		return baseApiService.put(`/api/v1/search-source-connectors/${id}`, updateConnectorResponse, {
			body: data,
		});
	};

	/**
	 * Delete a connector
	 */
	deleteConnector = async (request: DeleteConnectorRequest) => {
		const parsedRequest = deleteConnectorRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.delete(
			`/api/v1/search-source-connectors/${request.id}`,
			deleteConnectorResponse
		);
	};

	/**
	 * Index connector content
	 */
	indexConnector = async (request: IndexConnectorRequest) => {
		const parsedRequest = indexConnectorRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		const { connector_id, queryParams, body } = parsedRequest.data;

		// Transform query params to be string values
		const transformedQueryParams = Object.fromEntries(
			Object.entries(queryParams).map(([k, v]) => {
				return [k, String(v)];
			})
		);

		const queryString = new URLSearchParams(transformedQueryParams).toString();

		return baseApiService.post(
			`/api/v1/search-source-connectors/${connector_id}/index?${queryString}`,
			indexConnectorResponse,
			{
				body: body || {},
			}
		);
	};

	/**
	 * List GitHub repositories using a Personal Access Token
	 */
	listGitHubRepositories = async (request: ListGitHubRepositoriesRequest) => {
		const parsedRequest = listGitHubRepositoriesRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.post(`/api/v1/github/repositories`, listGitHubRepositoriesResponse, {
			body: parsedRequest.data,
		});
	};

	/**
	 * List Google Drive folders and files
	 */
	listGoogleDriveFolders = async (request: ListGoogleDriveFoldersRequest) => {
		const parsedRequest = listGoogleDriveFoldersRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		const { connector_id, parent_id } = parsedRequest.data;

		const queryParams = parent_id ? `?parent_id=${encodeURIComponent(parent_id)}` : "";

		return baseApiService.get(
			`/api/v1/connectors/${connector_id}/google-drive/folders${queryParams}`,
			listGoogleDriveFoldersResponse
		);
	};
}

export const connectorsApiService = new ConnectorsApiService();
