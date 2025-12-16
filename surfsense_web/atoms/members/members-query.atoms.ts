import { atomWithQuery } from "jotai-tanstack-query";
import { activeSearchSpaceIdAtom } from "@/atoms/search-spaces/search-space-query.atoms";
import { membersApiService } from "@/lib/apis/members-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";

export const membersAtom = atomWithQuery((get) => {
	const searchSpaceId = get(activeSearchSpaceIdAtom);

	return {
		queryKey: cacheKeys.members.all(searchSpaceId?.toString() ?? ""),
		enabled: !!searchSpaceId,
		staleTime: 5 * 60 * 1000, // 5 minutes
		queryFn: async () => {
			return membersApiService.getMembers({
				search_space_id: Number(searchSpaceId),
			});
		},
	};
});
