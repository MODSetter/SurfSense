import { atom } from "jotai";
import { atomWithQuery } from "jotai-tanstack-query";
import type { GetWorkspacesRequest } from "@/contracts/types/workspace.types";
import { workspacesApiService } from "@/lib/apis/workspaces-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";

export const activeWorkspaceIdAtom = atom<string | null>(null);

export const workspacesQueryParamsAtom = atom<GetWorkspacesRequest["queryParams"]>({
	skip: 0,
	limit: 10,
	owned_only: false,
});

export const workspacesAtom = atomWithQuery((get) => {
	const queryParams = get(workspacesQueryParamsAtom);

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
