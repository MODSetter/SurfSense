import { atomWithQuery } from "jotai-tanstack-query";
import { modelConnectionsApiService } from "@/lib/apis/model-connections-api.service";
import { isAuthenticated } from "@/lib/auth-utils";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { activeWorkspaceIdAtom } from "../workspaces/workspace-query.atoms";

export const globalModelConnectionsAtom = atomWithQuery(() => ({
	queryKey: cacheKeys.modelConnections.global(),
	enabled: isAuthenticated(),
	staleTime: 10 * 60 * 1000,
	queryFn: () => modelConnectionsApiService.getGlobalConnections(),
}));

export const globalLlmConfigStatusAtom = atomWithQuery(() => ({
	queryKey: cacheKeys.modelConnections.globalConfigStatus(),
	enabled: isAuthenticated(),
	staleTime: 60 * 60 * 1000,
	queryFn: () => modelConnectionsApiService.getGlobalLlmConfigStatus(),
}));

export const modelProvidersAtom = atomWithQuery(() => ({
	queryKey: cacheKeys.modelConnections.providers(),
	enabled: isAuthenticated(),
	staleTime: 60 * 60 * 1000,
	queryFn: () => modelConnectionsApiService.getModelProviders(),
}));

export const modelConnectionsAtom = atomWithQuery((get) => {
	const searchSpaceId = Number(get(activeWorkspaceIdAtom));
	return {
		queryKey: cacheKeys.modelConnections.all(searchSpaceId),
		enabled: !!searchSpaceId,
		staleTime: 5 * 60 * 1000,
		queryFn: () => modelConnectionsApiService.getConnections(searchSpaceId),
	};
});

export const modelRolesAtom = atomWithQuery((get) => {
	const searchSpaceId = Number(get(activeWorkspaceIdAtom));
	return {
		queryKey: cacheKeys.modelConnections.roles(searchSpaceId),
		enabled: !!searchSpaceId,
		staleTime: 5 * 60 * 1000,
		queryFn: () => modelConnectionsApiService.getModelRoles(searchSpaceId),
	};
});
