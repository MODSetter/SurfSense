import { atomWithQuery } from "jotai-tanstack-query";
import { activeWorkspaceIdAtom } from "@/atoms/workspaces/workspace-query.atoms";
import { automationsApiService } from "@/lib/apis/automations-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";

// First page of the active workspace's automations.
// Detail + paginated/parameterized reads live in hooks (see use-automation.ts,
// use-automation-runs.ts) so atoms stay tied to "current scope" and don't
// proliferate atom families for every (id, limit, offset) tuple.
const DEFAULT_LIMIT = 50;
const DEFAULT_OFFSET = 0;

export const automationsListAtom = atomWithQuery((get) => {
	const workspaceId = get(activeWorkspaceIdAtom);

	return {
		queryKey: cacheKeys.automations.list(Number(workspaceId ?? 0), DEFAULT_LIMIT, DEFAULT_OFFSET),
		enabled: !!workspaceId,
		staleTime: 60 * 1000,
		queryFn: async () => {
			if (!workspaceId) {
				return { items: [], total: 0 };
			}
			return automationsApiService.listAutomations({
				workspace_id: Number(workspaceId),
				limit: DEFAULT_LIMIT,
				offset: DEFAULT_OFFSET,
			});
		},
	};
});
