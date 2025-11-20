import { atomWithQuery } from "jotai-tanstack-query";
import { podcastsApiService } from "@/lib/apis/podcasts-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { globalPodcastsQueryParamsAtom } from "./ui.atoms";

export const podcastsAtom = atomWithQuery((get) => {
	const queryParams = get(globalPodcastsQueryParamsAtom);

	return {
		queryKey: cacheKeys.podcasts.globalQueryParams(queryParams),
		queryFn: async () => {
			return podcastsApiService.getPodcasts({
				queryParams: queryParams,
			});
		},
	};
});
