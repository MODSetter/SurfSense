import {
	type ConnectionCreateRequest,
	type ConnectionRead,
	type ConnectionUpdateRequest,
	connectionCreateRequest,
	connectionListResponse,
	connectionRead,
	connectionUpdateRequest,
	type ModelCreateRequest,
	type ModelPreviewRead,
	type ModelProviderRead,
	type ModelRead,
	type ModelRoles,
	type ModelTestPreviewRequest,
	type ModelsBulkUpdateRequest,
	type ModelUpdateRequest,
	modelCreateRequest,
	modelListResponse,
	modelPreviewListResponse,
	modelProviderListResponse,
	modelRead,
	modelRoles,
	modelTestPreviewRequest,
	modelsBulkUpdateRequest,
	modelUpdateRequest,
	type VerifyConnectionResponse,
	verifyConnectionResponse,
} from "@/contracts/types/model-connections.types";
import { ValidationError } from "../error";
import { baseApiService } from "./base-api.service";

class ModelConnectionsApiService {
	getGlobalConnections = async (): Promise<ConnectionRead[]> => {
		return baseApiService.get(`/api/v1/global-model-connections`, connectionListResponse);
	};

	getModelProviders = async (): Promise<ModelProviderRead[]> => {
		return baseApiService.get(`/api/v1/model-providers`, modelProviderListResponse);
	};

	getConnections = async (searchSpaceId: number): Promise<ConnectionRead[]> => {
		return baseApiService.get(
			`/api/v1/model-connections?search_space_id=${searchSpaceId}`,
			connectionListResponse
		);
	};

	createConnection = async (request: ConnectionCreateRequest): Promise<ConnectionRead> => {
		const parsed = connectionCreateRequest.safeParse(request);
		if (!parsed.success) {
			throw new ValidationError(parsed.error.issues.map((issue) => issue.message).join(", "));
		}
		return baseApiService.post(`/api/v1/model-connections`, connectionRead, {
			body: parsed.data,
		});
	};

	updateConnection = async (
		id: number,
		request: ConnectionUpdateRequest
	): Promise<ConnectionRead> => {
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

	verifyConnection = async (id: number): Promise<VerifyConnectionResponse> => {
		return baseApiService.post(`/api/v1/model-connections/${id}/verify`, verifyConnectionResponse);
	};

	discoverModels = async (id: number): Promise<ModelRead[]> => {
		return baseApiService.post(`/api/v1/model-connections/${id}/discover`, modelListResponse);
	};

	previewModels = async (request: ConnectionCreateRequest): Promise<ModelPreviewRead[]> => {
		const parsed = connectionCreateRequest.safeParse(request);
		if (!parsed.success) {
			throw new ValidationError(parsed.error.issues.map((issue) => issue.message).join(", "));
		}
		return baseApiService.post(
			`/api/v1/model-connections/discover-preview`,
			modelPreviewListResponse,
			{
				body: parsed.data,
			}
		);
	};

	testPreviewModel = async (request: ModelTestPreviewRequest): Promise<VerifyConnectionResponse> => {
		const parsed = modelTestPreviewRequest.safeParse(request);
		if (!parsed.success) {
			throw new ValidationError(parsed.error.issues.map((issue) => issue.message).join(", "));
		}
		return baseApiService.post(
			`/api/v1/model-connections/test-preview`,
			verifyConnectionResponse,
			{
				body: parsed.data,
			}
		);
	};

	addManualModel = async (
		connectionId: number,
		request: ModelCreateRequest
	): Promise<ModelRead> => {
		const parsed = modelCreateRequest.safeParse(request);
		if (!parsed.success) {
			throw new ValidationError(parsed.error.issues.map((issue) => issue.message).join(", "));
		}
		return baseApiService.post(`/api/v1/model-connections/${connectionId}/models`, modelRead, {
			body: parsed.data,
		});
	};

	updateModel = async (id: number, request: ModelUpdateRequest): Promise<ModelRead> => {
		const parsed = modelUpdateRequest.safeParse(request);
		if (!parsed.success) {
			throw new ValidationError(parsed.error.issues.map((issue) => issue.message).join(", "));
		}
		return baseApiService.put(`/api/v1/models/${id}`, modelRead, {
			body: parsed.data,
		});
	};

	bulkUpdateModels = async (
		connectionId: number,
		request: ModelsBulkUpdateRequest
	): Promise<ModelRead[]> => {
		const parsed = modelsBulkUpdateRequest.safeParse(request);
		if (!parsed.success) {
			throw new ValidationError(parsed.error.issues.map((issue) => issue.message).join(", "));
		}
		return baseApiService.request(
			`/api/v1/model-connections/${connectionId}/models`,
			modelListResponse,
			{
				method: "PATCH",
				headers: { "Content-Type": "application/json" },
				body: parsed.data,
			}
		);
	};

	testModel = async (id: number): Promise<VerifyConnectionResponse> => {
		return baseApiService.post(`/api/v1/models/${id}/test`, verifyConnectionResponse);
	};

	getModelRoles = async (searchSpaceId: number): Promise<ModelRoles> => {
		return baseApiService.get(`/api/v1/search-spaces/${searchSpaceId}/model-roles`, modelRoles);
	};

	updateModelRoles = async (searchSpaceId: number, roles: ModelRoles): Promise<ModelRoles> => {
		return baseApiService.put(`/api/v1/search-spaces/${searchSpaceId}/model-roles`, modelRoles, {
			body: roles,
		});
	};
}

export const modelConnectionsApiService = new ModelConnectionsApiService();
