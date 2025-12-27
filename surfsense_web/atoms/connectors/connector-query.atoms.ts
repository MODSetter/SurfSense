import { atomWithQuery } from "jotai-tanstack-query";
import { connectorsApiService } from "@/lib/apis/connectors-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { activeSearchSpaceIdAtom } from "../search-spaces/search-space-query.atoms";

export const connectorsAtom = atomWithQuery((get) => {
	const searchSpaceId = get(activeSearchSpaceIdAtom);

	return {
		queryKey: cacheKeys.connectors.all(searchSpaceId!),
		enabled: !!searchSpaceId,
		staleTime: 5 * 60 * 1000, // 5 minutes
		queryFn: async () => {
			return connectorsApiService.getConnectors({
				queryParams: {
					search_space_id: searchSpaceId!,
				},
			});
		},
	};
});
