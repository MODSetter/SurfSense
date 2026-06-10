import {
	type ConnectionCreateRequest,
	type ConnectionUpdateRequest,
	connectionCreateRequest,
	connectionListResponse,
	connectionRead,
	connectionUpdateRequest,
	type ModelRoles,
	type ModelUpdateRequest,
	modelListResponse,
	modelRead,
	modelRoles,
	modelUpdateRequest,
	verifyConnectionResponse,
} from "@/contracts/types/model-connections.types";
import { ValidationError } from "../error";
import { baseApiService } from "./base-api.service";

class ModelConnectionsApiService {
	getGlobalConnections = async () => {
		return baseApiService.get(`/api/v1/global-model-connections`, connectionListResponse);
	};

	getConnections = async (searchSpaceId: number) => {
		return baseApiService.get(
			`/api/v1/model-connections?search_space_id=${searchSpaceId}`,
			connectionListResponse
		);
	};

	createConnection = async (request: ConnectionCreateRequest) => {
		const parsed = connectionCreateRequest.safeParse(request);
		if (!parsed.success) {
			throw new ValidationError(parsed.error.issues.map((issue) => issue.message).join(", "));
		}
		return baseApiService.post(`/api/v1/model-connections`, connectionRead, {
			body: parsed.data,
		});
	};

	updateConnection = async (id: number, request: ConnectionUpdateRequest) => {
		const parsed = connectionUpdateRequest.safeParse(request);
		if (!parsed.success) {
			throw new ValidationError(parsed.error.issues.map((issue) => issue.message).join(", "));
		}
		return baseApiService.put(`/api/v1/model-connections/${id}`, connectionRead, {
			body: parsed.data,
		});
	};

	deleteConnection = async (id: number) => {
		return baseApiService.delete(`/api/v1/model-connections/${id}`, undefined);
	};

	verifyConnection = async (id: number) => {
		return baseApiService.post(`/api/v1/model-connections/${id}/verify`, verifyConnectionResponse);
	};

	discoverModels = async (id: number) => {
		return baseApiService.post(`/api/v1/model-connections/${id}/discover`, modelListResponse);
	};

	updateModel = async (id: number, request: ModelUpdateRequest) => {
		const parsed = modelUpdateRequest.safeParse(request);
		if (!parsed.success) {
			throw new ValidationError(parsed.error.issues.map((issue) => issue.message).join(", "));
		}
		return baseApiService.put(`/api/v1/models/${id}`, modelRead, {
			body: parsed.data,
		});
	};

	testModel = async (id: number) => {
		return baseApiService.post(`/api/v1/models/${id}/test`, verifyConnectionResponse);
	};

	getModelRoles = async (searchSpaceId: number) => {
		return baseApiService.get(`/api/v1/search-spaces/${searchSpaceId}/model-roles`, modelRoles);
	};

	updateModelRoles = async (searchSpaceId: number, roles: ModelRoles) => {
		return baseApiService.put(`/api/v1/search-spaces/${searchSpaceId}/model-roles`, modelRoles, {
			body: roles,
		});
	};
}

export const modelConnectionsApiService = new ModelConnectionsApiService();
