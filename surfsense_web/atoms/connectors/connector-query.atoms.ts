import { atomWithQuery } from "jotai-tanstack-query";
import { connectorsApiService } from "@/lib/apis/connectors-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { activeWorkspaceIdAtom } from "../workspaces/workspace-query.atoms";

export const connectorsAtom = atomWithQuery((get) => {
	const workspaceId = get(activeWorkspaceIdAtom);

	return {
		queryKey: cacheKeys.connectors.all(workspaceId!),
		enabled: !!workspaceId,
		staleTime: 5 * 60 * 1000, // 5 minutes
		queryFn: async () => {
			return connectorsApiService.getConnectors({
				queryParams: {
					workspace_id: workspaceId!,
				},
			});
		},
	};
});
