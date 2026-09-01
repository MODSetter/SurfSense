"use client";

import { useQuery } from "@tanstack/react-query";
import type { GitRemote } from "@/contracts/types/git-remote.types";
import { gitRemotesApiService } from "@/lib/apis/git-remotes-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";

/**
 * The connected repo's sync status, plus whether it needs the user's attention
 * (a conflict, a failed push, or a stale connection). Shares the settings page's
 * cache key so visiting either surface warms the other.
 *
 * ponytail: refetch is focus-driven (TanStack default). A push error raised while
 * this tab stays focused surfaces on the next focus/refetch, not instantly. Add a
 * refetchInterval here if we ever need near-real-time visibility.
 */
export function useGitRemoteStatus(workspaceId: number): {
	remote: GitRemote | undefined;
	needsAttention: boolean;
} {
	const { data } = useQuery({
		queryKey: cacheKeys.workspaces.gitRemotes(workspaceId),
		queryFn: () => gitRemotesApiService.list(workspaceId),
		enabled: Number.isFinite(workspaceId) && workspaceId > 0,
		staleTime: 30_000,
	});
	const remote = data?.[0];
	const needsAttention = Boolean(remote && (remote.last_error_code || remote.last_push_error));
	return { remote, needsAttention };
}
