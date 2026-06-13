import { atomWithMutation } from "jotai-tanstack-query";
import { toast } from "sonner";
import type {
	ConnectionCreateRequest,
	ConnectionRead,
	ConnectionUpdateRequest,
	ModelCreateRequest,
	ModelPreviewRead,
	ModelRead,
	ModelRoles,
	ModelsBulkUpdateRequest,
	ModelTestPreviewRequest,
	ModelUpdateRequest,
	VerifyConnectionResponse,
} from "@/contracts/types/model-connections.types";
import { modelConnectionsApiService } from "@/lib/apis/model-connections-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { queryClient } from "@/lib/query-client/client";
import { activeSearchSpaceIdAtom } from "../search-spaces/search-space-query.atoms";

function invalidateModelConnections(searchSpaceId: number) {
	queryClient.invalidateQueries({
		queryKey: cacheKeys.modelConnections.all(searchSpaceId),
	});
	queryClient.invalidateQueries({
		queryKey: cacheKeys.modelConnections.roles(searchSpaceId),
	});
}

function upsertModelConnection(searchSpaceId: number, connection: ConnectionRead) {
	queryClient.setQueryData<ConnectionRead[]>(
		cacheKeys.modelConnections.all(searchSpaceId),
		(current = []) => {
			if (current.some((item) => item.id === connection.id)) {
				return current.map((item) => (item.id === connection.id ? connection : item));
			}
			return [...current, connection];
		}
	);
}

export const createModelConnectionMutationAtom = atomWithMutation((get) => {
	const searchSpaceId = Number(get(activeSearchSpaceIdAtom));
	return {
		mutationKey: ["model-connections", "create"],
		mutationFn: (request: ConnectionCreateRequest) =>
			modelConnectionsApiService.createConnection(request),
		onSuccess: (connection: ConnectionRead, request: ConnectionCreateRequest) => {
			const resolvedSearchSpaceId = Number(
				request.search_space_id ?? connection.search_space_id ?? searchSpaceId
			);
			toast.success("Connection created");
			if (resolvedSearchSpaceId > 0) {
				upsertModelConnection(resolvedSearchSpaceId, connection);
				invalidateModelConnections(resolvedSearchSpaceId);
			}
		},
		onError: (error: Error) => toast.error(error.message || "Failed to create connection"),
	};
});

export const updateModelConnectionMutationAtom = atomWithMutation((get) => {
	const searchSpaceId = Number(get(activeSearchSpaceIdAtom));
	return {
		mutationKey: ["model-connections", "update"],
		mutationFn: ({ id, data }: { id: number; data: ConnectionUpdateRequest }) =>
			modelConnectionsApiService.updateConnection(id, data),
		onSuccess: () => {
			toast.success("Connection updated");
			invalidateModelConnections(searchSpaceId);
		},
		onError: (error: Error) => toast.error(error.message || "Failed to update connection"),
	};
});

export const deleteModelConnectionMutationAtom = atomWithMutation((get) => {
	const searchSpaceId = Number(get(activeSearchSpaceIdAtom));
	return {
		mutationKey: ["model-connections", "delete"],
		mutationFn: (id: number) => modelConnectionsApiService.deleteConnection(id),
		onSuccess: () => {
			toast.success("Connection deleted");
			invalidateModelConnections(searchSpaceId);
		},
		onError: (error: Error) => toast.error(error.message || "Failed to delete connection"),
	};
});

export const verifyModelConnectionMutationAtom = atomWithMutation((get) => {
	const searchSpaceId = Number(get(activeSearchSpaceIdAtom));
	return {
		mutationKey: ["model-connections", "verify"],
		mutationFn: (id: number) => modelConnectionsApiService.verifyConnection(id),
		onSuccess: (result: VerifyConnectionResponse) => {
			if (result.ok) {
				toast.success("Connection verified");
			} else {
				// Non-fatal: many providers lack a /models endpoint yet still serve
				// chat. Guide the user to add model IDs manually instead of alarming.
				toast.warning(
					result.message
						? `${result.message} Chat may still work — add model IDs manually.`
						: "Couldn't list models. Chat may still work — add model IDs manually."
				);
			}
			invalidateModelConnections(searchSpaceId);
		},
		onError: (error: Error) => toast.error(error.message || "Failed to verify connection"),
	};
});

export const discoverConnectionModelsMutationAtom = atomWithMutation((get) => {
	const searchSpaceId = Number(get(activeSearchSpaceIdAtom));
	return {
		mutationKey: ["model-connections", "discover"],
		mutationFn: (id: number) => modelConnectionsApiService.discoverModels(id),
		onSuccess: (models: ModelRead[]) => {
			toast.success(
				models.length ? `${models.length} models discovered` : "No models found for this connection"
			);
			invalidateModelConnections(searchSpaceId);
		},
		onError: (error: Error) => toast.error(error.message || "Failed to discover models"),
	};
});

export const previewConnectionModelsMutationAtom = atomWithMutation(() => {
	return {
		mutationKey: ["model-connections", "discover-preview"],
		mutationFn: (request: ConnectionCreateRequest) =>
			modelConnectionsApiService.previewModels(request),
		onSuccess: (_models: ModelPreviewRead[]) => {},
		onError: (error: Error) => toast.error(error.message || "Failed to discover models"),
	};
});

export const testPreviewModelMutationAtom = atomWithMutation(() => {
	return {
		mutationKey: ["model-connections", "test-preview"],
		mutationFn: (request: ModelTestPreviewRequest) =>
			modelConnectionsApiService.testPreviewModel(request),
		onSuccess: (result: VerifyConnectionResponse) => {
			if (!result.ok) {
				toast.error(result.message || "Model test failed");
			}
		},
		onError: (error: Error) => toast.error(error.message || "Failed to test model"),
	};
});

export const addManualModelMutationAtom = atomWithMutation((get) => {
	const searchSpaceId = Number(get(activeSearchSpaceIdAtom));
	return {
		mutationKey: ["models", "add-manual"],
		mutationFn: ({ connectionId, data }: { connectionId: number; data: ModelCreateRequest }) =>
			modelConnectionsApiService.addManualModel(connectionId, data),
		onSuccess: () => {
			toast.success("Model added");
			invalidateModelConnections(searchSpaceId);
		},
		onError: (error: Error) => toast.error(error.message || "Failed to add model"),
	};
});

export const updateModelMutationAtom = atomWithMutation((get) => {
	const searchSpaceId = Number(get(activeSearchSpaceIdAtom));
	return {
		mutationKey: ["models", "update"],
		mutationFn: ({ id, data }: { id: number; data: ModelUpdateRequest }) =>
			modelConnectionsApiService.updateModel(id, data),
		onSuccess: () => invalidateModelConnections(searchSpaceId),
		onError: (error: Error) => toast.error(error.message || "Failed to update model"),
	};
});

export const bulkUpdateModelsMutationAtom = atomWithMutation((get) => {
	const searchSpaceId = Number(get(activeSearchSpaceIdAtom));
	return {
		mutationKey: ["models", "bulk-update"],
		mutationFn: ({ connectionId, data }: { connectionId: number; data: ModelsBulkUpdateRequest }) =>
			modelConnectionsApiService.bulkUpdateModels(connectionId, data),
		onSuccess: () => invalidateModelConnections(searchSpaceId),
		onError: (error: Error) => toast.error(error.message || "Failed to update models"),
	};
});

export const testModelMutationAtom = atomWithMutation((get) => {
	const searchSpaceId = Number(get(activeSearchSpaceIdAtom));
	return {
		mutationKey: ["models", "test"],
		mutationFn: (id: number) => modelConnectionsApiService.testModel(id),
		onSuccess: (result: VerifyConnectionResponse) => {
			if (result.ok) toast.success("Model test succeeded");
			else toast.error(result.message || "Model test failed");
			invalidateModelConnections(searchSpaceId);
		},
		onError: (error: Error) => toast.error(error.message || "Failed to test model"),
	};
});

export const updateModelRolesMutationAtom = atomWithMutation((get) => {
	const searchSpaceId = Number(get(activeSearchSpaceIdAtom));
	return {
		mutationKey: ["model-roles", "update"],
		mutationFn: (roles: ModelRoles) =>
			modelConnectionsApiService.updateModelRoles(searchSpaceId, roles),
		onSuccess: () => {
			queryClient.invalidateQueries({
				queryKey: cacheKeys.modelConnections.roles(searchSpaceId),
			});
		},
		onError: (error: Error) => toast.error(error.message || "Failed to update model roles"),
	};
});
