import { atomWithMutation } from "jotai-tanstack-query";
import { toast } from "sonner";
import { activeSearchSpaceIdAtom } from "@/atoms/seach-spaces/seach-space-queries.atom";
import type {
	DeletePodcastRequest,
	GeneratePodcastRequest,
	Podcast,
} from "@/contracts/types/podcast.types";
import { podcastsApiService } from "@/lib/apis/podcasts-api.service";
import { getBearerToken } from "@/lib/auth-utils";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { queryClient } from "@/lib/query-client/client";
import { globalPodcastsQueryParamsAtom } from "./ui.atoms";

export const deletePodcastMutationAtom = atomWithMutation((get) => {
	const searchSpaceId = get(activeSearchSpaceIdAtom);
	const authToken = getBearerToken();
	const podcastsQueryParams = get(globalPodcastsQueryParamsAtom);

	return {
		mutationKey: cacheKeys.podcasts.globalQueryParams(podcastsQueryParams),
		enabled: !!searchSpaceId && !!authToken,
		mutationFn: async (request: DeletePodcastRequest) => {
			return podcastsApiService.deletePodcast(request);
		},

		onSuccess: (_, request: DeletePodcastRequest) => {
			toast.success("Podcast deleted successfully");
			queryClient.setQueryData(
				cacheKeys.podcasts.globalQueryParams(podcastsQueryParams),
				(oldData: Podcast[]) => {
					return oldData.filter((podcast) => podcast.id !== request.id);
				}
			);
		},
	};
});

export const generatePodcastMutationAtom = atomWithMutation((get) => {
	const searchSpaceId = get(activeSearchSpaceIdAtom);
	const authToken = getBearerToken();
	const podcastsQueryParams = get(globalPodcastsQueryParamsAtom);

	return {
		mutationKey: cacheKeys.podcasts.globalQueryParams(podcastsQueryParams),
		enabled: !!searchSpaceId && !!authToken,
		mutationFn: async (request: GeneratePodcastRequest) => {
			return podcastsApiService.generatePodcast(request);
		},
	};
});
