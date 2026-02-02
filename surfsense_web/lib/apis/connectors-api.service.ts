import {
	type CreateConnectorRequest,
	createConnectorRequest,
	createConnectorResponse,
	type DeleteConnectorRequest,
	type DiscordChannel,
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
	listDiscordChannelsResponse,
	listGitHubRepositoriesRequest,
	listGitHubRepositoriesResponse,
	listGoogleDriveFoldersRequest,
	listGoogleDriveFoldersResponse,
	listSlackChannelsResponse,
	type SlackChannel,
	type UpdateConnectorRequest,
	updateConnectorRequest,
	updateConnectorResponse,
} from "@/contracts/types/connector.types";
import type {
	CreateMCPConnectorRequest,
	GetMCPConnectorsRequest,
	MCPConnectorRead,
	MCPServerConfig,
	MCPTestConnectionResponse,
	UpdateMCPConnectorRequest,
} from "@/contracts/types/mcp.types";
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

		// Transform query params to be string values, filtering out undefined/null
		const transformedQueryParams = parsedRequest.data.queryParams
			? Object.fromEntries(
					Object.entries(parsedRequest.data.queryParams)
						.filter(([_, v]) => v !== undefined && v !== null)
						.map(([k, v]) => {
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

		// Transform query params to be string values, filtering out undefined/null
		const transformedQueryParams = Object.fromEntries(
			Object.entries(queryParams)
				.filter(([_, v]) => v !== undefined && v !== null)
				.map(([k, v]) => {
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

		// Transform query params to be string values, filtering out undefined/null
		const transformedQueryParams = Object.fromEntries(
			Object.entries(queryParams)
				.filter(([_, v]) => v !== undefined && v !== null)
				.map(([k, v]) => {
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

	/**
	 * List Composio Google Drive folders and files
	 */
	listComposioDriveFolders = async (request: ListGoogleDriveFoldersRequest) => {
		const parsedRequest = listGoogleDriveFoldersRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		const { connector_id, parent_id } = parsedRequest.data;

		const queryParams = parent_id ? `?parent_id=${encodeURIComponent(parent_id)}` : "";

		return baseApiService.get(
			`/api/v1/connectors/${connector_id}/composio-drive/folders${queryParams}`,
			listGoogleDriveFoldersResponse
		);
	};

	// =============================================================================
	// MCP Connector Methods
	// =============================================================================

	/**
	 * Get all MCP connectors for a search space
	 */
	getMCPConnectors = async (request: GetMCPConnectorsRequest) => {
		const { search_space_id } = request.queryParams;

		const queryString = new URLSearchParams({
			search_space_id: String(search_space_id),
		}).toString();

		return baseApiService.get<MCPConnectorRead[]>(`/api/v1/connectors/mcp?${queryString}`);
	};

	/**
	 * Get a single MCP connector by ID
	 */
	getMCPConnector = async (connectorId: number) => {
		return baseApiService.get<MCPConnectorRead>(`/api/v1/connectors/mcp/${connectorId}`);
	};

	/**
	 * Create a new MCP connector
	 */
	createMCPConnector = async (request: CreateMCPConnectorRequest) => {
		const { data, queryParams } = request;

		const queryString = new URLSearchParams({
			search_space_id: String(queryParams.search_space_id),
		}).toString();

		return baseApiService.post<MCPConnectorRead>(
			`/api/v1/connectors/mcp?${queryString}`,
			undefined,
			{
				body: data,
			}
		);
	};

	/**
	 * Update an existing MCP connector
	 */
	updateMCPConnector = async (request: UpdateMCPConnectorRequest) => {
		const { id, data } = request;

		return baseApiService.put<MCPConnectorRead>(`/api/v1/connectors/mcp/${id}`, undefined, {
			body: data,
		});
	};

	/**
	 * Delete an MCP connector
	 */
	deleteMCPConnector = async (connectorId: number) => {
		return baseApiService.delete<void>(`/api/v1/connectors/mcp/${connectorId}`);
	};

	/**
	 * Test MCP server connection and retrieve available tools
	 */
	testMCPConnection = async (serverConfig: MCPServerConfig) => {
		return baseApiService.post<MCPTestConnectionResponse>(
			"/api/v1/connectors/mcp/test",
			undefined,
			{
				body: serverConfig,
			}
		);
	};

	// =============================================================================
	// Slack Connector Methods
	// =============================================================================

	/**
	 * Get Slack channels with bot membership status
	 */
	getSlackChannels = async (connectorId: number) => {
		return baseApiService.get(
			`/api/v1/slack/connector/${connectorId}/channels`,
			listSlackChannelsResponse
		);
	};

	// =============================================================================
	// Discord Connector Methods
	// =============================================================================

	/**
	 * Get Discord text channels for a connector
	 */
	getDiscordChannels = async (connectorId: number) => {
		return baseApiService.get(
			`/api/v1/discord/connector/${connectorId}/channels`,
			listDiscordChannelsResponse
		);
	};
}

export type { SlackChannel, DiscordChannel };

export const connectorsApiService = new ConnectorsApiService();
