"use client";

import { useQuery } from "@tanstack/react-query";
import type { GitRemote } from "@/contracts/types/git-remote.types";
import { gitRemotesApiService } from "@/lib/apis/git-remotes-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";

/** The connected repo's sync status and whether it needs the user's attention. */
export function useGitRemoteStatus(workspaceId: number): {
	remote: GitRemote | undefined;
	needsAttention: boolean;
} {
	const { data } = useQuery({
		queryKey: cacheKeys.workspaces.gitRemotes(workspaceId),
		queryFn: () => gitRemotesApiService.list(workspaceId),
		enabled: Number.isFinite(workspaceId) && workspaceId > 0,
		staleTime: 30_000,
		// ponytail: polls every 8s until the mount folder resolves; an empty repo
		// never resolves, so cap it or invalidate on tree changes if it matters.
		refetchInterval: (query) => {
			const remote = query.state.data?.[0];
			return remote && remote.mount_folder_id == null ? 8_000 : false;
		},
	});
	const remote = data?.[0];
	const needsAttention = Boolean(remote && (remote.last_error_code || remote.last_push_error));
	return { remote, needsAttention };
}
