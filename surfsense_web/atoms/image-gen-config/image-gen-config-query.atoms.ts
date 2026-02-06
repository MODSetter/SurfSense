import { atomWithQuery } from "jotai-tanstack-query";
import { imageGenConfigApiService } from "@/lib/apis/image-gen-config-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { activeSearchSpaceIdAtom } from "../search-spaces/search-space-query.atoms";

/**
 * Query atom for fetching user-created image gen configs for the active search space
 */
export const imageGenConfigsAtom = atomWithQuery((get) => {
	const searchSpaceId = get(activeSearchSpaceIdAtom);

	return {
		queryKey: cacheKeys.imageGenConfigs.all(Number(searchSpaceId)),
		enabled: !!searchSpaceId,
		staleTime: 5 * 60 * 1000, // 5 minutes
		queryFn: async () => {
			return imageGenConfigApiService.getConfigs(Number(searchSpaceId));
		},
	};
});

/**
 * Query atom for fetching global image gen configs (from YAML, negative IDs)
 */
export const globalImageGenConfigsAtom = atomWithQuery(() => {
	return {
		queryKey: cacheKeys.imageGenConfigs.global(),
		staleTime: 10 * 60 * 1000, // 10 minutes - global configs rarely change
		queryFn: async () => {
			return imageGenConfigApiService.getGlobalConfigs();
		},
	};
});
