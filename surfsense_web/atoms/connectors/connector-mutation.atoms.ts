import { atomWithMutation } from "jotai-tanstack-query";
import type {
	CreateConnectorRequest,
	DeleteConnectorRequest,
	GetConnectorsResponse,
	IndexConnectorRequest,
	IndexConnectorResponse,
	UpdateConnectorRequest,
} from "@/contracts/types/connector.types";
import { connectorsApiService } from "@/lib/apis/connectors-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { queryClient } from "@/lib/query-client/client";
import { activeWorkspaceIdAtom } from "../workspaces/workspace-query.atoms";

export const createConnectorMutationAtom = atomWithMutation((get) => {
	const workspaceId = get(activeWorkspaceIdAtom);

	return {
		mutationKey: cacheKeys.connectors.all(workspaceId ?? ""),
		enabled: !!workspaceId,
		mutationFn: async (request: CreateConnectorRequest) => {
			return connectorsApiService.createConnector(request);
		},

		onSuccess: () => {
			if (!workspaceId) return;
			queryClient.invalidateQueries({
				queryKey: cacheKeys.connectors.all(workspaceId),
			});
		},
	};
});

export const updateConnectorMutationAtom = atomWithMutation((get) => {
	const workspaceId = get(activeWorkspaceIdAtom);

	return {
		mutationKey: cacheKeys.connectors.all(workspaceId ?? ""),
		enabled: !!workspaceId,
		mutationFn: async (request: UpdateConnectorRequest) => {
			return connectorsApiService.updateConnector(request);
		},

		onSuccess: (_, request: UpdateConnectorRequest) => {
			if (!workspaceId) return;
			queryClient.invalidateQueries({
				queryKey: cacheKeys.connectors.all(workspaceId),
			});
			queryClient.invalidateQueries({
				queryKey: cacheKeys.connectors.byId(String(request.id)),
			});
		},
	};
});

export const deleteConnectorMutationAtom = atomWithMutation((get) => {
	const workspaceId = get(activeWorkspaceIdAtom);

	return {
		mutationKey: cacheKeys.connectors.all(workspaceId ?? ""),
		enabled: !!workspaceId,
		mutationFn: async (request: DeleteConnectorRequest) => {
			return connectorsApiService.deleteConnector(request);
		},

		onSuccess: (_, request: DeleteConnectorRequest) => {
			if (!workspaceId) return;
			queryClient.setQueryData(
				cacheKeys.connectors.all(workspaceId),
				(oldData: GetConnectorsResponse | undefined) => {
					if (!oldData) return oldData;
					return oldData.filter((connector) => connector.id !== request.id);
				}
			);
			queryClient.invalidateQueries({
				queryKey: cacheKeys.connectors.byId(String(request.id)),
			});
		},
	};
});

export const indexConnectorMutationAtom = atomWithMutation((get) => {
	const workspaceId = get(activeWorkspaceIdAtom);

	return {
		mutationKey: cacheKeys.connectors.index(),
		enabled: !!workspaceId,
		mutationFn: async (request: IndexConnectorRequest) => {
			return connectorsApiService.indexConnector(request);
		},

		onSuccess: (response: IndexConnectorResponse) => {
			if (!workspaceId) return;
			queryClient.invalidateQueries({
				queryKey: cacheKeys.connectors.all(workspaceId),
			});
			queryClient.invalidateQueries({
				queryKey: cacheKeys.connectors.byId(String(response.connector_id)),
			});
		},
	};
});
