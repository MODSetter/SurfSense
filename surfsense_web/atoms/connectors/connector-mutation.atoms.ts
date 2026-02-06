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
import { activeSearchSpaceIdAtom } from "../search-spaces/search-space-query.atoms";

export const createConnectorMutationAtom = atomWithMutation((get) => {
	const searchSpaceId = get(activeSearchSpaceIdAtom);

	return {
		mutationKey: cacheKeys.connectors.all(searchSpaceId ?? ""),
		enabled: !!searchSpaceId,
		mutationFn: async (request: CreateConnectorRequest) => {
			return connectorsApiService.createConnector(request);
		},

		onSuccess: () => {
			if (!searchSpaceId) return;
			queryClient.invalidateQueries({
				queryKey: cacheKeys.connectors.all(searchSpaceId),
			});
		},
	};
});

export const updateConnectorMutationAtom = atomWithMutation((get) => {
	const searchSpaceId = get(activeSearchSpaceIdAtom);

	return {
		mutationKey: cacheKeys.connectors.all(searchSpaceId ?? ""),
		enabled: !!searchSpaceId,
		mutationFn: async (request: UpdateConnectorRequest) => {
			return connectorsApiService.updateConnector(request);
		},

		onSuccess: (_, request: UpdateConnectorRequest) => {
			if (!searchSpaceId) return;
			queryClient.invalidateQueries({
				queryKey: cacheKeys.connectors.all(searchSpaceId),
			});
			queryClient.invalidateQueries({
				queryKey: cacheKeys.connectors.byId(String(request.id)),
			});
		},
	};
});

export const deleteConnectorMutationAtom = atomWithMutation((get) => {
	const searchSpaceId = get(activeSearchSpaceIdAtom);

	return {
		mutationKey: cacheKeys.connectors.all(searchSpaceId ?? ""),
		enabled: !!searchSpaceId,
		mutationFn: async (request: DeleteConnectorRequest) => {
			return connectorsApiService.deleteConnector(request);
		},

		onSuccess: (_, request: DeleteConnectorRequest) => {
			if (!searchSpaceId) return;
			queryClient.setQueryData(
				cacheKeys.connectors.all(searchSpaceId),
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
	const searchSpaceId = get(activeSearchSpaceIdAtom);

	return {
		mutationKey: cacheKeys.connectors.index(),
		enabled: !!searchSpaceId,
		mutationFn: async (request: IndexConnectorRequest) => {
			return connectorsApiService.indexConnector(request);
		},

		onSuccess: (response: IndexConnectorResponse) => {
			if (!searchSpaceId) return;
			queryClient.invalidateQueries({
				queryKey: cacheKeys.connectors.all(searchSpaceId),
			});
			queryClient.invalidateQueries({
				queryKey: cacheKeys.connectors.byId(String(response.connector_id)),
			});
		},
	};
});
