import { atomWithQuery } from "jotai-tanstack-query";
import { activeWorkspaceIdAtom } from "@/atoms/workspaces/workspace-query.atoms";
import { automationsApiService } from "@/lib/apis/automations-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";

// First page of the active search space's automations.
// Detail + paginated/parameterized reads live in hooks (see use-automation.ts,
// use-automation-runs.ts) so atoms stay tied to "current scope" and don't
// proliferate atom families for every (id, limit, offset) tuple.
const DEFAULT_LIMIT = 50;
const DEFAULT_OFFSET = 0;

export const automationsListAtom = atomWithQuery((get) => {
	const searchSpaceId = get(activeWorkspaceIdAtom);

	return {
		queryKey: cacheKeys.automations.list(Number(searchSpaceId ?? 0), DEFAULT_LIMIT, DEFAULT_OFFSET),
		enabled: !!searchSpaceId,
		staleTime: 60 * 1000,
		queryFn: async () => {
			if (!searchSpaceId) {
				return { items: [], total: 0 };
			}
			return automationsApiService.listAutomations({
				workspace_id: Number(searchSpaceId),
				limit: DEFAULT_LIMIT,
				offset: DEFAULT_OFFSET,
			});
		},
	};
});
