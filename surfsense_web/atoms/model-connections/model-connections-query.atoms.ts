import { atomWithQuery } from "jotai-tanstack-query";
import { modelConnectionsApiService } from "@/lib/apis/model-connections-api.service";
import { getBearerToken } from "@/lib/auth-utils";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { activeSearchSpaceIdAtom } from "../search-spaces/search-space-query.atoms";

export const globalModelConnectionsAtom = atomWithQuery(() => ({
	queryKey: cacheKeys.modelConnections.global(),
	enabled: !!getBearerToken(),
	staleTime: 10 * 60 * 1000,
	queryFn: () => modelConnectionsApiService.getGlobalConnections(),
}));

export const modelProvidersAtom = atomWithQuery(() => ({
	queryKey: cacheKeys.modelConnections.providers(),
	enabled: !!getBearerToken(),
	staleTime: 60 * 60 * 1000,
	queryFn: () => modelConnectionsApiService.getModelProviders(),
}));

export const modelConnectionsAtom = atomWithQuery((get) => {
	const searchSpaceId = Number(get(activeSearchSpaceIdAtom));
	return {
		queryKey: cacheKeys.modelConnections.all(searchSpaceId),
		enabled: !!searchSpaceId,
		staleTime: 5 * 60 * 1000,
		queryFn: () => modelConnectionsApiService.getConnections(searchSpaceId),
	};
});

export const modelRolesAtom = atomWithQuery((get) => {
	const searchSpaceId = Number(get(activeSearchSpaceIdAtom));
	return {
		queryKey: cacheKeys.modelConnections.roles(searchSpaceId),
		enabled: !!searchSpaceId,
		staleTime: 5 * 60 * 1000,
		queryFn: () => modelConnectionsApiService.getModelRoles(searchSpaceId),
	};
});
