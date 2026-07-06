import { atomWithQuery } from "jotai-tanstack-query";
import { activeWorkspaceIdAtom } from "@/atoms/workspaces/workspace-query.atoms";
import { chatThreadsApiService } from "@/lib/apis/chat-threads-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";

export const publicChatSnapshotsAtom = atomWithQuery((get) => {
	const searchSpaceId = get(activeWorkspaceIdAtom);

	return {
		queryKey: cacheKeys.publicChatSnapshots.bySearchSpace(Number(searchSpaceId) || 0),
		enabled: !!searchSpaceId,
		staleTime: 5 * 60 * 1000,
		queryFn: async () => {
			if (!searchSpaceId) {
				return { snapshots: [] };
			}
			return chatThreadsApiService.listPublicChatSnapshotsForSearchSpace({
				workspace_id: Number(searchSpaceId),
			});
		},
	};
});
