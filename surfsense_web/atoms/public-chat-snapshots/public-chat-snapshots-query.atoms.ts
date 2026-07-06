import { atomWithQuery } from "jotai-tanstack-query";
import { activeWorkspaceIdAtom } from "@/atoms/workspaces/workspace-query.atoms";
import { chatThreadsApiService } from "@/lib/apis/chat-threads-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";

export const publicChatSnapshotsAtom = atomWithQuery((get) => {
	const workspaceId = get(activeWorkspaceIdAtom);

	return {
		queryKey: cacheKeys.publicChatSnapshots.byWorkspace(Number(workspaceId) || 0),
		enabled: !!workspaceId,
		staleTime: 5 * 60 * 1000,
		queryFn: async () => {
			if (!workspaceId) {
				return { snapshots: [] };
			}
			return chatThreadsApiService.listPublicChatSnapshotsForWorkspace({
				workspace_id: Number(workspaceId),
			});
		},
	};
});
