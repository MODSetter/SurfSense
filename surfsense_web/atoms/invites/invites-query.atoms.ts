import { atomWithQuery } from "jotai-tanstack-query";
import { activeWorkspaceIdAtom } from "@/atoms/workspaces/workspace-query.atoms";
import { invitesApiService } from "@/lib/apis/invites-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";

export const invitesAtom = atomWithQuery((get) => {
	const workspaceId = get(activeWorkspaceIdAtom);

	return {
		queryKey: cacheKeys.invites.all(workspaceId?.toString() ?? ""),
		enabled: !!workspaceId,
		staleTime: 5 * 60 * 1000, // 5 minutes
		queryFn: async () => {
			if (!workspaceId) {
				return [];
			}
			return invitesApiService.getInvites({
				workspace_id: Number(workspaceId),
			});
		},
	};
});
