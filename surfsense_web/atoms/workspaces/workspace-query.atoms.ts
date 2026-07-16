import { atom } from "jotai";
import { atomWithQuery } from "jotai-tanstack-query";
import type { GetWorkspacesRequest } from "@/contracts/types/workspace.types";
import { workspacesApiService } from "@/lib/apis/workspaces-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";

export const activeWorkspaceIdAtom = atom<string | null>(null);

export const workspaceLimitsAtom = atomWithQuery(() => {
	return {
		queryKey: cacheKeys.workspaces.limits,
		staleTime: Infinity,
		queryFn: async () => {
			return workspacesApiService.getWorkspaceLimits();
		},
	};
});

export const workspacesAtom = atomWithQuery((get) => {
	const workspaceLimits = get(workspaceLimitsAtom).data;
	const queryParams: GetWorkspacesRequest["queryParams"] = {
		skip: 0,
		...(workspaceLimits ? { limit: workspaceLimits.max_workspaces_per_user } : {}),
		owned_only: false,
	};

	return {
		queryKey: cacheKeys.workspaces.withQueryParams(queryParams),
		staleTime: 5 * 60 * 1000,
		queryFn: async () => {
			return workspacesApiService.getWorkspaces({
				queryParams,
			});
		},
	};
});
